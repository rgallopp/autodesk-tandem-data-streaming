"""Small, independently written APS/Tandem reader; see docs/REFERENCES.md."""

import base64
import binascii
import os
from pathlib import Path
import time
from urllib.parse import quote

import requests
from measurements import FIELDS

BASE = "https://developer.api.autodesk.com"
ROOT = Path(__file__).resolve().parents[1]
CREDENTIAL_NAMES = ("APS_CLIENT_ID", "APS_CLIENT_SECRET")


class ApiError(RuntimeError):
    """Safe to display: never includes URLs, request bodies, headers, or tokens."""


def read_credentials(path=None):
    """Read two literal single-line keys from root .env without changing os.environ.

    Existing process variables (including empty ones) win. No interpolation,
    shell execution, directory searching, or third-party dependency is involved.
    """
    existing = {name: os.environ[name] for name in CREDENTIAL_NAMES if name in os.environ}
    if len(existing) == len(CREDENTIAL_NAMES):
        return existing
    path = ROOT / ".env" if path is None else Path(path)
    values = {}
    try:
        if path.exists():
            with path.open(encoding="utf-8-sig") as source:
                for number, raw in enumerate(source, 1):
                    line = raw.strip()
                    if not line or line.startswith("#"):
                        continue
                    name, separator, value = line.partition("=")
                    name, value = name.strip(), value.strip()
                    if not separator or name not in CREDENTIAL_NAMES or name in values:
                        raise ApiError(f"Invalid .env assignment on line {number}; use each APS credential key once.")
                    if value.startswith(('"', "'")):
                        if len(value) < 2 or value[-1] != value[0]:
                            raise ApiError(f"Invalid .env quotes on line {number}; use a single-line value.")
                        value = value[1:-1]
                    values[name] = value
    except (OSError, UnicodeError):
        raise ApiError("Cannot read the project-root .env; check file access and UTF-8 encoding.") from None
    values.update(existing)
    return {name: values.get(name, "") for name in CREDENTIAL_NAMES}


def source_field(mapping):
    """Expose only a known flat payload key, never arbitrary integration settings."""
    if not isinstance(mapping, dict) or not isinstance(mapping.get("path"), str):
        raise ApiError("Unexpected source mapping response. Recheck saved mappings.")
    path = mapping["path"]
    for fields in FIELDS.values():
        for field in fields.values():
            if path in (field, "$." + field, "$['" + field + "']", '$["' + field + '"]'):
                return field
    return None


def full_key(text):
    """Normalize Tandem's 20-byte short key or 24-byte full logical key."""
    if not isinstance(text, str):
        raise ValueError("Connection key must be text.")
    try:
        raw = base64.b64decode(text + "=" * (-len(text) % 4), altchars=b"-_", validate=True)
    except (ValueError, binascii.Error):
        raise ValueError("Invalid connection key.") from None
    if len(raw) == 20:
        raw = b"\x01\x00\x00\x00" + raw
    if len(raw) != 24:
        raise ValueError("Expected a 20-byte short key or 24-byte full key.")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


class TandemReader:
    def __init__(self, session=None, region=None):
        self.session = session or requests.Session()
        self.region = region
        self.token = None
        self.expires = 0

    def close(self):
        self.session.close()

    def _json(self, method, url, label, **kwargs):
        try:
            with self.session.request(method, url, timeout=(10, 60),
                                      allow_redirects=False, **kwargs) as response:
                if not 200 <= response.status_code < 300:
                    raise ApiError(f"{label}: HTTP {response.status_code}. See troubleshooting.")
                return response.json()
        except (requests.RequestException, ValueError):
            raise ApiError(f"{label}: network failure or invalid JSON; credentials are hidden.") from None

    def _access_token(self):
        if self.token and time.monotonic() < self.expires:
            return self.token
        credentials = read_credentials()
        client_id = credentials["APS_CLIENT_ID"]
        secret = credentials["APS_CLIENT_SECRET"]
        if not client_id or not secret:
            raise ApiError("Fill APS_CLIENT_ID and APS_CLIENT_SECRET in root .env or the process environment.")
        data = self._json("POST", BASE + "/authentication/v2/token", "APS authentication",
                          auth=(client_id, secret),
                          data={"grant_type": "client_credentials", "scope": "data:read"})
        if not isinstance(data, dict) or not isinstance(data.get("access_token"), str):
            raise ApiError("APS authentication: missing access token.")
        self.token = data["access_token"]
        try:
            lifetime = float(data.get("expires_in", 300))
        except (TypeError, ValueError):
            raise ApiError("APS authentication: invalid token lifetime.") from None
        self.expires = time.monotonic() + max(0, lifetime - 60)
        return self.token

    def request(self, method, path, **kwargs):
        headers = {"Authorization": "Bearer " + self._access_token()}
        if self.region:
            headers["Region"] = self.region
        return self._json(method, BASE + "/tandem/v1/" + path, "Tandem API",
                          headers=headers, **kwargs)

    def discover(self, facility_urn):
        """Join facility links, parameter schema, connections, and saved source fields.

        Display names are metadata, not matching keys. The scan POST reads metadata;
        it does not ingest measurements or change the facility.
        """
        if not isinstance(facility_urn, str) or not facility_urn.startswith("urn:adsk.dtt:"):
            raise ValueError("Use the facility URN beginning urn:adsk.dtt:.")
        facility = self.request("GET", "twins/" + quote(facility_urn, safe=""))
        model = facility_urn.replace("urn:adsk.dtt:", "urn:adsk.dtm:", 1)
        if (not isinstance(facility, dict) or not isinstance(facility.get("links"), list)
                or any(not isinstance(link, dict) for link in facility["links"])):
            raise ApiError("Unexpected facility links response; discovery stopped.")
        if not any(link.get("modelId") == model for link in facility["links"]):
            raise ApiError("Facility default model was not found.")
        encoded = quote(model, safe="")
        schema = self.request("GET", f"modeldata/{encoded}/schema")
        scanned = self.request("POST", f"modeldata/{encoded}/scan",
                               json={"families": ["n"], "includeHistory": False, "skipArrays": True})
        configs = self.request("GET", f"models/{encoded}/stream-configs")
        if (not isinstance(schema, dict) or not isinstance(schema.get("attributes"), list)
                or not isinstance(scanned, list) or not isinstance(configs, list)):
            raise ApiError("Unexpected discovery response; no export created.")
        attributes = {}
        for prop in schema["attributes"]:
            if not isinstance(prop, dict) or not isinstance(prop.get("id"), str):
                raise ApiError("Unexpected schema attribute response; discovery stopped.")
            if prop["id"] in attributes:
                raise ApiError("Duplicate schema parameter ID; discovery stopped.")
            for name in ("name", "forgeUnit", "forgeSymbol"):
                if prop.get(name) is not None and not isinstance(prop[name], str):
                    raise ApiError("Unexpected parameter metadata; discovery stopped.")
            attributes[prop["id"]] = prop
        mappings = {}
        for config in configs:
            if not isinstance(config, dict):
                raise ApiError("Unexpected stream configuration response; discovery stopped.")
            try:
                key = full_key(config.get("elementId"))
            except ValueError:
                raise ApiError("Invalid stream configuration key; discovery stopped.") from None
            settings = config.get("streamSettings")
            if settings is None:
                settings = {}
            if not isinstance(settings, dict):
                raise ApiError("Unexpected stream settings response; discovery stopped.")
            mapping = settings.get("sourceMapping")
            if mapping is None:
                mapping = {}
            if not isinstance(mapping, dict) or any(not isinstance(pid, str) for pid in mapping):
                raise ApiError("Unexpected source mappings response; discovery stopped.")
            if key in mappings:
                raise ApiError("Duplicate stream configuration key; discovery stopped.")
            mappings[key] = {pid: source_field(value) for pid, value in mapping.items()}
        connections = []
        seen = set()
        for item in scanned:
            if not isinstance(item, dict) or item.get("n:a") != 0x01000003:
                continue
            try:
                key = full_key(item.get("k"))
            except ValueError:
                raise ApiError("Invalid discovered connection key; discovery stopped.") from None
            if key in seen:
                raise ApiError("Duplicate discovered connection key; discovery stopped.")
            seen.add(key)
            parameters = []
            for pid in mappings.get(key, {}):
                prop = attributes.get(pid, {})
                parameters.append({"parameter_id": pid, "name": prop.get("name", ""),
                                   "unit": prop.get("forgeUnit", ""),
                                   "symbol": prop.get("forgeSymbol", ""),
                                   "source_field": mappings[key][pid]})
            connections.append({"connection_key": key, "name": item.get("n:!n") or item.get("n:n", ""),
                                "parameters": parameters})
        # Never return the raw stream configuration: it can contain integration details.
        return {"facility_urn": facility_urn, "model_urn": model,
                "connections": connections, "attributes": attributes}

    def history(self, model, connection, parameter, start_ms, end_ms, page_size=1000):
        """Read [start_ms, end_ms), paging separately inside UTC calendar days.

        Live small-page queries can return an empty response before data in a later
        day. An empty/short page must therefore not end the whole multi-day export.
        Overlap/deduplication handles inclusive or exclusive lower bounds within
        each day; each day is also locally filtered to a half-open interval.
        """
        if not 2 <= page_size <= 1000 or start_ms >= end_ms:
            raise ValueError("Use page size 2..1000 and increasing query bounds.")
        path = f"timeseries/models/{quote(model, safe='')}/streams/{quote(full_key(connection), safe='')}"
        day_ms = 24 * 60 * 60 * 1000
        window_start = start_ms
        result = {}
        while window_start < end_ms:
            window_end = min(end_ms, (window_start // day_ms + 1) * day_ms)
            cursor = window_start - 1
            while cursor < window_end:
                data = self.request("GET", path, params={"from": cursor, "to": window_end,
                                    "substream": parameter, "limit": page_size, "sort": "asc"})
                if not isinstance(data, dict) or any(k != parameter for k in data):
                    raise ApiError("Unexpected series response; export stopped.")
                values = data.get(parameter, {})
                if not isinstance(values, dict):
                    raise ApiError("Unexpected measurement response; export stopped.")
                page = {}
                for timestamp, value in values.items():
                    try:
                        stamp = int(timestamp)
                    except (ValueError, TypeError):
                        raise ApiError("Invalid returned timestamp; export stopped.") from None
                    if str(stamp) != str(timestamp) or stamp < cursor or stamp > window_end:
                        raise ApiError("API did not respect query bounds; export stopped.")
                    page[stamp] = value
                for stamp, value in page.items():
                    if window_start <= stamp < window_end:
                        if stamp in result and result[stamp] != value:
                            raise ApiError("History changed during paging; rerun after ingestion stops.")
                        result[stamp] = value
                if not page and cursor == window_start - 1:
                    # A look-behind can land in an exhausted previous storage day.
                    # Retry at this window's exact lower edge before declaring it empty.
                    cursor = window_start
                    continue
                if not page:
                    break  # This day is exhausted; still visit every later UTC day.
                cursor = max(page) + (1 if cursor in page else 0)
            window_start = window_end
        return sorted(result.items())

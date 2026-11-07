"""Preview or replay complete HVAC CSV batches to two Tandem connections.

Workflow adaptation of Autodesk's Individual ingestion example; independently
implemented CSV routing and validation. Attribution: docs/REFERENCES.md.
"""

import argparse
import csv
from datetime import datetime, timezone
from getpass import getpass
import json
import math
import os
from pathlib import Path
import sys
import time
from urllib.parse import unquote, urlsplit

import requests
from measurements import FIELDS

# Resolve default file locations relative to this script, regardless of the
# working directory. Explicit command-line paths can override these defaults.
ROOT = Path(__file__).resolve().parents[1]

class CsvError(ValueError):
    """Controlled diagnostics containing line numbers, never raw cell values."""


def read_batches(path):
    """Group by source timestamp, routing labels through FIELDS without unit conversion.

    Return chronological complete groups and the number skipped. Source timestamps
    identify batches locally; payload dictionaries contain numeric measurements only.
    """
    groups = {}
    dates = {}
    timezone_aware = None
    # utf-8-sig also accepts a UTF-8 byte-order mark, often present in Excel CSVs.
    with path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        required = {"timestamp", "equipment_id", "sensor", "value"}
        if (not required.issubset(reader.fieldnames or [])
                or len(reader.fieldnames) != len(set(reader.fieldnames))):
            raise CsvError("CSV needs distinct headings including timestamp, equipment_id, sensor, value.")
        for number, row in enumerate(reader, 2):
            if None in row or any(not isinstance(row.get(key), str) or not row[key].strip()
                                  for key in required):
                raise CsvError(f"Missing cells or extra CSV cells on line {number}.")
            equipment, sensor = row["equipment_id"], row["sensor"]
            if equipment not in FIELDS or sensor not in FIELDS[equipment]:
                raise CsvError(f"Unknown equipment or sensor on CSV line {number}.")
            # Equivalent instants with different text remain separate source groups.
            stamp = row["timestamp"]
            try:
                date = datetime.fromisoformat(stamp)
                if "T" not in stamp and " " not in stamp:
                    raise ValueError()
                value = float(row["value"])
            except ValueError:
                raise CsvError(f"Invalid timestamp or numeric value on CSV line {number}.") from None
            aware = date.utcoffset() is not None
            if timezone_aware is not None and aware != timezone_aware:
                raise CsvError(f"Mixed timezone-aware and timezone-free timestamps on CSV line {number}.")
            timezone_aware = aware
            dates[stamp] = date
            if not math.isfinite(value):
                raise CsvError(f"Nonfinite value on CSV line {number}.")
            # Build: timestamp -> equipment -> {Tandem field: numeric value}.
            payload = groups.setdefault(stamp, {}).setdefault(equipment, {})
            key = FIELDS[equipment][sensor]
            if key in payload:
                raise CsvError(f"Duplicate measurement on CSV line {number}.")
            payload[key] = value
    # Require every mapped measurement across equipment; never fill missing values.
    complete = [(stamp, group) for stamp, group in groups.items()
                if all(set(group.get(eq, {})) == set(fields.values())
                       for eq, fields in FIELDS.items())]
    complete.sort(key=lambda batch: dates[batch[0]])
    return complete, len(groups) - len(complete)


def destination(url):
    """Separate authentication so exception messages cannot reveal secrets."""
    # Accept only the expected HTTPS Tandem stream URL, including its password.
    parsed = urlsplit(url.strip())
    if (parsed.scheme != "https" or parsed.hostname != "tandem.autodesk.com"
            or parsed.port not in (None, 443) or not parsed.password
            or not parsed.path.startswith("/api/v1/timeseries/models/")
            or "/streams/" not in parsed.path or parsed.query or parsed.fragment):
        raise ValueError("Expected an individual Tandem ingestion URL with credentials.")
    # Remove credentials from the URL and decode them for HTTP Basic Auth.
    # Requests receives the clean endpoint and credentials as separate arguments.
    endpoint = f"https://tandem.autodesk.com{parsed.path}"
    return endpoint, (unquote(parsed.username or ""), unquote(parsed.password))


def connections(config_path):
    """Find one ingestion URL per equipment item without displaying credentials."""
    # Configuration is optional; environment variables take precedence below.
    config = {}
    if config_path.exists():
        with config_path.open(encoding="utf-8-sig") as source:
            config = json.load(source)
        if not isinstance(config, dict):
            raise ValueError("Expected configuration object.")
    result = {}
    for equipment in FIELDS:
        variable = {"ahu-01": "TANDEM_AHU_URL", "vav-3": "TANDEM_VAV_URL"}.get(equipment, "")
        # Lookup order: environment variable -> config.json -> hidden prompt.
        url = (os.environ.get(variable) if variable else None) or config.get(equipment)
        if not url:
            url = getpass(f"Paste {equipment} ingestion URL (hidden): ")
        if not isinstance(url, str):
            raise ValueError("Expected URL text.")
        result[equipment] = destination(url)
    # Prevent both equipment items from accidentally posting to the same stream.
    if len({target[0] for target in result.values()}) != len(result):
        raise ValueError("Each equipment item must use a different connection.")
    return result


def send_measurements(target, stamp, equipment, payload, log_path):
    """POST numeric fields once, logging source/client times and sanitized HTTP status.

    An accepted request does not prove retention. A timeout leaves delivery unknown;
    no automatic retry is safe here. Genuine history comes from read_readings.py.
    """
    # Open the log before sending so an unusable log prevents a POST.
    log_path.parent.mkdir(parents=True, exist_ok=True)
    columns = ["source_timestamp", "send_time_utc", "equipment_id", "field", "value", "http_result"]
    with log_path.open("a", newline="", encoding="utf-8") as log:
        needs_header = log.tell() == 0
        endpoint, auth = target
        sent = datetime.now(timezone.utc).isoformat()
        try:
            response = requests.post(endpoint, auth=auth, json=payload,
                                     timeout=(10, 30), allow_redirects=False)
            status = str(response.status_code)
            success = 200 <= response.status_code < 300
            response.close()
        except requests.RequestException:
            status, success = "NETWORK_ERROR", False
        writer = csv.DictWriter(log, fieldnames=columns)
        if needs_header:
            writer.writeheader()
        for key, value in payload.items():
            writer.writerow(dict(zip(columns, [stamp, sent, equipment, key, value, status])))
    return status, success


def main(argv=None):
    # Default settings: preview six batches, with a 60-second delay between
    # batches during live sending. --send is required to make HTTP requests.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--send", action="store_true", help="Enable live HTTP POSTs")
    parser.add_argument("--steps", type=int, default=6)
    parser.add_argument("--interval", type=float, default=60)
    parser.add_argument("--csv", type=Path, default=ROOT / "data" / "demo_hvac.csv")
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "config.json")
    parser.add_argument("--log", type=Path, default=ROOT / "logs" / "hvac_send_log.csv")
    args = parser.parse_args(argv)
    # Validate replay settings before reading connections or attempting a send.
    if args.steps < 1 or not math.isfinite(args.interval) or args.interval < 60:
        parser.error("steps must be positive and interval must be at least 60 seconds")
    batches, skipped = read_batches(args.csv)
    if args.steps > len(batches):
        parser.error(f"Only {len(batches)} complete batches are available.")
    print(f"Found {len(batches)} complete batches; skipped {skipped} incomplete timestamps.")
    selected = batches[:args.steps]
    # Preview mode prints the exact JSON field/value content without requesting
    # credentials, sending HTTP requests, or writing a send log.
    if not args.send:
        for stamp, group in selected:
            print(f"Source timestamp: {stamp} (not included in POST)")
            for equipment, payload in group.items():
                print(f"  {equipment}: {json.dumps(payload, sort_keys=True)}")
        print("Preview only: no data sent.")
        return 0
    # Live mode resolves credentials once, then sends two requests per batch.
    targets = connections(args.config)
    fields_per_batch = sum(map(len, FIELDS.values()))
    print(f"Run settings: batches={args.steps}, interval_seconds={args.interval:g}, "
          f"requests={args.steps * len(FIELDS)}, values={args.steps * fields_per_batch}, "
          f"values_per_series={args.steps}", flush=True)
    print(f"Run started UTC: {datetime.now(timezone.utc).isoformat()}", flush=True)
    accepted_values = 0
    complete = False
    try:
        for index, (stamp, group) in enumerate(selected):
            # Fixed delay between batches; source spacing is not reproduced.
            if index:
                time.sleep(args.interval)
            for equipment in FIELDS:
                attempted = datetime.now(timezone.utc).isoformat()
                status, success = send_measurements(
                    targets[equipment], stamp, equipment, group[equipment], args.log)
                print(f"Batch {index + 1}/{args.steps}, {equipment}: {status}; "
                      f"request UTC {attempted}; values {len(group[equipment])}", flush=True)
                if not success:
                    print("Stopped. Check the local log before rerunning; no automatic retry.")
                    return 1
                accepted_values += len(group[equipment])
        complete = True
        return 0
    finally:
        print(f"Run ended UTC: {datetime.now(timezone.utc).isoformat()}", flush=True)
        print(f"Run outcome: {'complete' if complete else 'incomplete'}; "
              f"HTTP-accepted measurement values: {accepted_values}. "
              "Verify stored history through charts and API readback.", flush=True)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except CsvError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
    except (ValueError, OSError, EOFError):
        # Report validation, file-access, and missing-input errors without secrets.
        print("Unable to continue. Check CSV, configuration, URLs, and file access; credentials are hidden.",
              file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("Stopped by user; check the log before rerunning.")
        sys.exit(130)

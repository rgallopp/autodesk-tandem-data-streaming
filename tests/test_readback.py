"""Synthetic API fixtures exercise discovery/export; no actual facility is queried."""

import base64
import copy
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from measurements import FIELDS
import read_readings as exporter
from tandem_api import ApiError, TandemReader, full_key
import tandem_api


KEYS = [base64.urlsafe_b64encode(bytes([n]) * 20).decode().rstrip("=") for n in [1, 2]]


def fixture():
    connections, attributes, config = [], {}, {"facility_urn": "urn:adsk.dtt:example", "connections": {}}
    count = 0
    for key, (equipment, fields) in zip(KEYS, FIELDS.items()):
        params, mapped = {}, []
        for field in fields.values():
            count += 1
            pid = f"z:{count}"
            params[field] = pid
            mapped.append({"parameter_id": pid, "source_field": field, "name": field, "unit": "test-unit"})
            attributes[pid] = {"id": pid, "name": field, "forgeUnit": "test-unit"}
        connections.append({"connection_key": full_key(key), "name": equipment, "parameters": mapped})
        config["connections"][equipment] = {"connection_key": full_key(key), "parameters": params}
    return config, {"facility_urn": config["facility_urn"], "model_urn": "urn:adsk.dtm:example",
                    "connections": connections, "attributes": attributes}


class ReadbackTests(unittest.TestCase):
    def test_root_env_literal_values_and_environment_precedence(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            (folder / ".env").write_text(
                '# synthetic fixture only\nAPS_CLIENT_ID="fixture-id"\n'
                "APS_CLIENT_SECRET='fixture#${literal}=value'\n", encoding="utf-8")
            with mock.patch.object(tandem_api, "ROOT", folder), mock.patch.dict(os.environ, {}, clear=True):
                self.assertEqual(tandem_api.read_credentials(), {
                    "APS_CLIENT_ID": "fixture-id", "APS_CLIENT_SECRET": "fixture#${literal}=value"})
                self.assertNotIn("APS_CLIENT_ID", os.environ)
                with mock.patch.dict(os.environ, {"APS_CLIENT_ID": "process-fixture"}):
                    values = tandem_api.read_credentials()
                    self.assertEqual(values["APS_CLIENT_ID"], "process-fixture")
                    self.assertEqual(values["APS_CLIENT_SECRET"], "fixture#${literal}=value")
                with mock.patch.dict(os.environ, {"APS_CLIENT_SECRET": ""}):
                    self.assertEqual(tandem_api.read_credentials()["APS_CLIENT_SECRET"], "")

    def test_invalid_env_errors_never_echo_values(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(os.environ, {}, clear=True):
            path = Path(folder) / ".env"
            for contents in ['APS_CLIENT_SECRET="sensitive-fixture\n',
                             'APS_CLIENT_ID=a\nAPS_CLIENT_ID=sensitive-fixture\n',
                             'UNKNOWN=sensitive-fixture\n']:
                path.write_text(contents)
                with self.assertRaises(ApiError) as error:
                    tandem_api.read_credentials(path)
                self.assertNotIn("sensitive-fixture", str(error.exception))
            path.write_bytes(b'APS_CLIENT_SECRET=\xff')
            with self.assertRaises(ApiError):
                tandem_api.read_credentials(path)

    def test_blank_env_prevents_authentication_request(self):
        reader = TandemReader()
        try:
            with tempfile.TemporaryDirectory() as folder:
                folder = Path(folder)
                (folder / ".env").write_text('APS_CLIENT_ID=\nAPS_CLIENT_SECRET=\n')
                with mock.patch.object(tandem_api, "ROOT", folder), mock.patch.dict(os.environ, {}, clear=True), \
                        mock.patch.object(reader, "_json") as request, self.assertRaises(ApiError):
                    reader._access_token()
                request.assert_not_called()
        finally:
            reader.close()

    def test_discovery_uses_private_facility_before_ids_are_filled(self):
        _, discovery = fixture()
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            config = folder / "readback.json"
            config.write_text(json.dumps({"facility_urn": "urn:adsk.dtt:example", "connections": {}}))
            original = config.read_bytes()
            reader = mock.Mock()
            reader.discover.return_value = discovery
            with mock.patch.object(exporter, "TandemReader", return_value=reader):
                self.assertEqual(exporter.main(["--discover", "--config", str(config),
                                               "--output", str(folder / "discovery.json")]), 0)
            reader.discover.assert_called_once_with("urn:adsk.dtt:example")
            reader.history.assert_not_called()
            self.assertEqual(config.read_bytes(), original)

    def test_timezone_bounds_and_milliseconds(self):
        self.assertEqual(exporter.utc_bound("2026-11-05T12:00:00.123Z"),
                         exporter.utc_bound("2026-11-05T07:00:00.123-05:00"))
        self.assertEqual(exporter.utc_text(123), "1970-01-01T00:00:00.123Z")
        for text in ["2026-11-05T12:00:00", "2026-11-05T12:00:00.123456Z"]:
            with self.assertRaises(ValueError):
                exporter.utc_bound(text)

    def test_full_and_short_keys(self):
        self.assertEqual(full_key(full_key(KEYS[0])), full_key(KEYS[0]))
        with self.assertRaises(ValueError):
            full_key("not-an-id")

    def test_pages_with_inclusive_and_exclusive_bounds_and_server_cap(self):
        points = {1000: 501.25, 2000: 502.25, 3000: 503.25, 4000: 504.25, 5000: 505.25}
        for inclusive, cap in [(False, 1), (False, 2), (True, 1), (True, 2)]:
            with self.subTest(inclusive=inclusive, cap=cap):
                reader = TandemReader()
                def query(method, path, params):
                    cursor = params["from"]
                    subset = [(k, v) for k, v in points.items()
                              if (k >= cursor if inclusive else k > cursor) and k <= params["to"]]
                    # Server returns fewer than the requested limit: still must continue.
                    return {"z:1": {str(k): v for k, v in subset[:cap]}}
                with mock.patch.object(reader, "request", side_effect=query) as request:
                    values = reader.history("urn:adsk.dtm:x", KEYS[0], "z:1", 1000, 5000, 1000)
                self.assertEqual(values, list(points.items())[:4])
                self.assertGreater(request.call_count, 1)
                reader.close()

    def test_empty_day_does_not_hide_later_days_or_midnight_points(self):
        day = 24 * 60 * 60 * 1000
        points = {1000: 1.0, 2000: 2.0, 2 * day: 3.0, 2 * day + 1500: 4.0, 3 * day: 5.0}
        for inclusive, cap in [(False, 1), (False, 2), (True, 1), (True, 2)]:
            with self.subTest(inclusive=inclusive, cap=cap):
                reader = TandemReader()
                def query(method, path, params):
                    cursor = params["from"]
                    if inclusive and (cursor + 1) % day == 0:
                        # Live behavior: a look-behind in the preceding day can be
                        # empty even when querying the exact new-day edge finds data.
                        return {"z:1": {}}
                    bucket = (cursor + 1) // day
                    # Reproduce a sparse API response: exhausted days return empty
                    # even though later days contain points inside the overall range.
                    values = [(k, v) for k, v in points.items() if k // day == bucket
                              and (k >= cursor if inclusive else k > cursor) and k <= params["to"]]
                    return {"z:1": {str(k): v for k, v in values[:cap]}}
                try:
                    with mock.patch.object(reader, "request", side_effect=query) as request:
                        result = reader.history("urn:adsk.dtm:x", KEYS[0], "z:1", 1000, 3 * day + 1, 2)
                    self.assertEqual(result, list(points.items()))
                    self.assertTrue(any(call.kwargs["params"]["from"] == day - 1 for call in request.call_args_list))
                finally:
                    reader.close()

    def test_midnight_upper_boundary_is_exclusive_without_losing_next_day(self):
        day = 24 * 60 * 60 * 1000
        points = {day - 1: 1.0, day: 2.0, day + 1: 3.0}
        reader = TandemReader()
        def query(method, path, params):
            # Model an inclusive API upper edge; the export's upper edge is exclusive.
            values = [(k, v) for k, v in points.items() if params["from"] <= k <= params["to"]]
            return {"z:1": {str(k): v for k, v in values[:params["limit"]]}}
        try:
            for size in (2, 1000):
                with self.subTest(size=size), mock.patch.object(reader, "request", side_effect=query):
                    self.assertEqual(reader.history("urn:adsk.dtm:x", KEYS[0], "z:1", day - 100, day, size),
                                     [(day - 1, 1.0)])
                    self.assertEqual(reader.history("urn:adsk.dtm:x", KEYS[0], "z:1", day - 100, day + 1, size),
                                     [(day - 1, 1.0), (day, 2.0)])
        finally:
            reader.close()

    def test_bad_response_and_changed_overlap_fail(self):
        reader = TandemReader()
        responses = [{"z:1": {"1000": 10, "2000": 20}}, {"z:1": {"2000": 99}}]
        with mock.patch.object(reader, "request", side_effect=responses), self.assertRaises(ApiError):
            reader.history("urn:adsk.dtm:x", KEYS[0], "z:1", 1000, 4000, 2)
        with mock.patch.object(reader, "request", return_value={"unexpected": {}}), self.assertRaises(ApiError):
            reader.history("urn:adsk.dtm:x", KEYS[0], "z:1", 1000, 4000)
        reader.close()

    def test_six_series_export_uses_api_values_and_reports_empty(self):
        config, discovery = fixture()
        reader = mock.Mock()
        reader.discover.return_value = discovery
        reader.history.side_effect = lambda model, key, pid, *args: [(1123, 900 + int(pid[2:]))]
        rows, summary = exporter.collect(reader, config, 1000, 2000, 2)
        self.assertEqual(len(rows), 6)
        self.assertEqual(len(summary["counts"]), 6)
        self.assertEqual(set(r["equipment_id"] for r in rows), set(FIELDS))
        self.assertEqual({r["value"] for r in rows}, set(range(901, 907)))
        self.assertEqual({r["timestamp_epoch_ms"] for r in rows}, {1123})
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "api.csv"
            exporter.write_export(path, rows, summary)
            with path.open(encoding="utf-8", newline="") as source:
                self.assertEqual(len(list(csv.DictReader(source))), 6)
            with self.assertRaises(ValueError):
                exporter.write_export(path, rows, summary)
        reader.history.return_value = []
        reader.history.side_effect = None
        rows, summary = exporter.collect(reader, config, 1000, 2000)
        self.assertEqual(rows, [])
        self.assertEqual(len(summary["empty_series"]), 6)

    def test_all_mappings_validated_before_history(self):
        config, discovery = fixture()
        discovery["connections"][1]["parameters"] = []
        reader = mock.Mock()
        reader.discover.return_value = discovery
        with self.assertRaises(ValueError):
            exporter.collect(reader, config, 1000, 2000)
        reader.history.assert_not_called()

    def test_auth_scope_expiry_and_sanitized_failures(self):
        reader = TandemReader()
        with mock.patch.dict("os.environ", {"APS_CLIENT_ID": "id", "APS_CLIENT_SECRET": "never-print-me"}), \
             mock.patch.object(reader, "_json", return_value={"access_token": "token", "expires_in": 3600}) as request:
            reader._access_token()
            reader._access_token()
            self.assertEqual(request.call_count, 1)
            self.assertEqual(request.call_args.kwargs["data"]["scope"], "data:read")
            reader.expires = 0
            reader._access_token()
            self.assertEqual(request.call_count, 2)
        response = mock.MagicMock()
        response.__enter__.return_value.status_code = 403
        response.__enter__.return_value.text = "never-print-me"
        with mock.patch.object(reader.session, "request", return_value=response), self.assertRaises(ApiError) as error:
            reader._json("GET", "https://example.invalid", "Tandem API")
        self.assertNotIn("never-print-me", str(error.exception))
        self.assertIn("403", str(error.exception))
        reader.close()

    def test_discovery_filters_header_and_normalizes_keys(self):
        reader = TandemReader()
        data = [
            {"links": [{"modelId": "urn:adsk.dtm:example"}]},
            {"attributes": [{"id": "z:1", "name": "Temperature", "forgeUnit": "celsius"}]},
            ["header", {"k": KEYS[0], "n:a": 0x01000003, "n:!n": "Connection"},
             {"k": KEYS[1], "n:a": 0}],
            [{"elementId": full_key(KEYS[0]), "streamSettings": {
                "sourceMapping": {"z:1": {"path": "zone_temperature"}}, "private-integration": "never-export"}}],
        ]
        with mock.patch.object(reader, "request", side_effect=data):
            result = reader.discover("urn:adsk.dtt:example")
        self.assertEqual(len(result["connections"]), 1)
        self.assertEqual(result["connections"][0]["parameters"][0]["parameter_id"], "z:1")
        self.assertNotIn("sourceMapping", json.dumps(result))
        self.assertNotIn("never-export", json.dumps(result))
        self.assertEqual(result["connections"][0]["parameters"][0]["source_field"], "zone_temperature")
        reader.close()

    def test_custom_display_names_and_swapped_fields(self):
        config, discovery = fixture()
        for prop in discovery["attributes"].values():
            prop["name"] = "Custom display label " + prop["id"]
        reader = mock.Mock()
        reader.discover.return_value = discovery
        reader.history.return_value = [(1123, 42.5)]
        rows, _ = exporter.collect(reader, config, 1000, 2000)
        self.assertEqual(len(rows), 6)
        self.assertTrue(all(row["parameter_name"].startswith("Custom display label") for row in rows))
        params = config["connections"]["ahu-01"]["parameters"]
        a, b, _ = params
        params[a], params[b] = params[b], params[a]
        reader.history.reset_mock()
        with self.assertRaises(ValueError):
            exporter.collect(reader, config, 1000, 2000)
        reader.history.assert_not_called()

    def test_malformed_discovery_shapes_are_safe_errors(self):
        valid = [
            {"links": [{"modelId": "urn:adsk.dtm:example"}]},
            {"attributes": [{"id": "z:1"}]},
            ["header", {"k": KEYS[0], "n:a": 0x01000003}],
            [{"elementId": KEYS[0], "streamSettings": {"sourceMapping": {"z:1": {"path": "zone_temperature"}}}}],
        ]
        cases = [(0, {"links": [None]}), (0, {"links": None}),
                 (1, {"attributes": [None]}), (3, [None]),
                 (3, [{"elementId": KEYS[0], "streamSettings": []}]),
                 (3, [{"elementId": KEYS[0], "streamSettings": {"sourceMapping": []}}]),
                 (2, [{"n:a": 0x01000003}])]
        for index, replacement in cases:
            data = copy.deepcopy(valid)
            data[index] = replacement
            with self.subTest(index=index), TandemReader().session as session:
                reader = TandemReader(session=session)
                with mock.patch.object(reader, "request", side_effect=data), self.assertRaises(ApiError):
                    reader.discover("urn:adsk.dtt:example")

    def test_unknown_source_paths_are_not_disclosed(self):
        from tandem_api import source_field
        self.assertIsNone(source_field({"path": "private-integration-marker"}))
        self.assertEqual(source_field({"path": "$.zone_temperature"}), "zone_temperature")

    def test_export_write_failures_remove_only_new_files(self):
        config, discovery = fixture()
        reader = mock.Mock()
        reader.discover.return_value = discovery
        reader.history.return_value = [(1123, 42.5)]
        rows, summary = exporter.collect(reader, config, 1000, 2000)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "result.csv"
            summary_path = path.with_suffix(".csv.summary.json")
            original_open = Path.open
            for failing in (path, summary_path):
                def fail_open(candidate, *args, **kwargs):
                    if candidate == failing:
                        raise PermissionError("synthetic write error")
                    return original_open(candidate, *args, **kwargs)
                with mock.patch.object(Path, "open", fail_open), self.assertRaises(OSError):
                    exporter.write_export(path, rows, summary)
                self.assertFalse(path.exists())
                self.assertFalse(summary_path.exists())
            summary_path.write_text("preserve")
            with self.assertRaises(ValueError):
                exporter.write_export(path, rows, summary)
            self.assertEqual(summary_path.read_text(), "preserve")
            self.assertFalse(path.exists())

    def test_cli_auth_discovery_and_history_transport_together(self):
        config, discovery = fixture()
        transport = mock.Mock()
        stream_configs = []
        for item in config["connections"].values():
            stream_configs.append({"elementId": item["connection_key"], "streamSettings": {
                "sourceMapping": {pid: {"path": field} for field, pid in item["parameters"].items()}}})

        def response(method, url, **kwargs):
            if url.endswith("/authentication/v2/token"):
                self.assertEqual(kwargs["data"]["scope"], "data:read")
                data = {"access_token": "synthetic-token", "expires_in": 3600}
            elif "/twins/" in url:
                data = {"links": [{"modelId": discovery["model_urn"]}]}
            elif url.endswith("/schema"):
                data = {"attributes": list(discovery["attributes"].values())}
            elif url.endswith("/scan"):
                self.assertEqual(method, "POST")  # Read-only metadata scan, not ingestion.
                data = ["header"] + [{"k": c["connection_key"], "n:a": 0x01000003,
                                      "n:!n": c["name"]} for c in discovery["connections"]]
            elif url.endswith("/stream-configs"):
                data = stream_configs
            else:
                self.assertEqual(method, "GET")
                self.assertIn("/streams/", url)
                params = kwargs["params"]
                data = {params["substream"]: {"1123": 99.5} if params["from"] <= 1123 else {}}
            result = mock.MagicMock()
            result.__enter__.return_value.status_code = 200
            result.__enter__.return_value.json.return_value = data
            return result

        transport.request.side_effect = response
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            settings = folder / "config.json"
            settings.write_text(json.dumps(config))
            output = folder / "transport.csv"
            with mock.patch.dict("os.environ", {"APS_CLIENT_ID": "synthetic-id", "APS_CLIENT_SECRET": "synthetic-secret"}), \
                    mock.patch.object(tandem_api.requests, "Session", return_value=transport):
                result = exporter.main(["--config", str(settings), "--from-utc", "1970-01-01T00:00:01Z",
                                        "--to-utc", "1970-01-01T00:00:02Z", "--output", str(output)])
            self.assertEqual(result, 0)
            with output.open(newline="", encoding="utf-8") as source:
                rows = list(csv.DictReader(source))
            self.assertEqual(len(rows), 6)
            self.assertEqual({row["value"] for row in rows}, {"99.5"})
            self.assertEqual({row["timestamp_epoch_ms"] for row in rows}, {"1123"})
            self.assertNotIn("synthetic-secret", output.read_text())
        transport.close.assert_called_once()

    def test_cli_export_and_empty_interval_use_only_mocked_api(self):
        config, discovery = fixture()
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            settings = folder / "config.json"
            settings.write_text(json.dumps(config))
            for count, expected_exit in [(1, 0), (0, 3)]:
                reader = mock.Mock()
                reader.discover.return_value = discovery
                reader.history.return_value = [(1123, 99.5)] if count else []
                output = folder / f"result-{count}.csv"
                with mock.patch.object(exporter, "TandemReader", return_value=reader):
                    result = exporter.main(["--config", str(settings), "--from-utc", "1970-01-01T00:00:01Z",
                                            "--to-utc", "1970-01-01T00:00:02Z", "--output", str(output)])
                self.assertEqual(result, expected_exit)
                self.assertEqual(reader.history.call_count, 6)
                with output.open(newline="", encoding="utf-8") as source:
                    self.assertEqual(len(list(csv.DictReader(source))), 6 * count)
                reader.close.assert_called_once()

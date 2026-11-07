"""Offline CSV, payload, pacing, and failure checks; HTTP is mocked, not live proof."""

import csv
import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("sender", ROOT/"scripts/ingest-data-individual-stream-from-csv.py")
sender = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sender)

class SenderTests(unittest.TestCase):
    def test_dataset(self):
        batches, skipped = sender.read_batches(ROOT/"data/demo_hvac.csv")
        self.assertEqual((len(batches), skipped), (120, 0))
        self.assertTrue(all(isinstance(v, float) for p in batches[0][1].values() for v in p.values()))

    def test_http_success_and_stop_on_failure(self):
        for status, calls, count in [(200, 2, 6), (404, 1, 3)]:
            with self.subTest(status=status), tempfile.TemporaryDirectory() as directory:
                log = Path(directory)/"nested/send.csv"
                targets = {eq: ("https://example.invalid", ()) for eq in sender.FIELDS}
                with mock.patch.object(sender, "connections", return_value=targets), mock.patch.object(sender.requests, "post", return_value=mock.Mock(status_code=status)) as post:
                    result = sender.main(["--send", "--steps", "1", "--log", str(log)])
                    self.assertEqual(result, 0 if status == 200 else 1)
                    self.assertEqual(post.call_count, calls)
                    self.assertFalse(post.call_args.kwargs["allow_redirects"])
                with log.open(newline="", encoding="utf-8") as stream:
                    rows = list(csv.DictReader(stream))
                self.assertEqual(len(rows), count)
                self.assertEqual({r["http_result"] for r in rows}, {str(status)})

    def test_unusable_log_prevents_request(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(sender.requests, "post") as post:
            with self.assertRaises(OSError):
                sender.send_measurements(("https://example.invalid", ()), "source", "ahu-01", {}, Path(directory))
            post.assert_not_called()

    def csv_case(self, text):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "input.csv"
            path.write_text(text, encoding="utf-8")
            return sender.read_batches(path)

    def test_missing_invalid_duplicate_and_inconsistent_rows(self):
        header = "timestamp,equipment_id,sensor,value\n"
        valid = "2026-01-01T00:00:00Z,ahu-01,Chilled Water Temperature,54\n"
        cases = [
            "2026-01-01T00:00:00Z,ahu-01,Chilled Water Temperature\n",
            valid.replace(",54", ",NaN"), valid.replace(",54", ",Infinity"),
            valid.replace(",54", ",secret-invalid-number"),
            valid.replace("2026-01-01T00:00:00Z", "bad-date"), valid + valid,
            valid + valid.replace("2026-01-01T00:00:00Z", "2026-01-01T00:15:00"),
        ]
        for rows in cases:
            with self.subTest(rows=rows), self.assertRaises(sender.CsvError) as error:
                self.csv_case(header + rows)
            self.assertIn("line", str(error.exception))
            self.assertNotIn("secret-invalid-number", str(error.exception))

    def test_incomplete_groups_are_skipped_without_filling(self):
        with (ROOT / "data/demo_hvac.csv").open(encoding="utf-8") as source:
            rows = list(csv.DictReader(source))[:12]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "input.csv"
            with path.open("w", newline="", encoding="utf-8") as target:
                writer = csv.DictWriter(target, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows[:6] + rows[7:])
            batches, skipped = sender.read_batches(path)
        self.assertEqual((len(batches), skipped), (1, 1))
        self.assertEqual(batches[0][0], rows[0]["timestamp"])

    def test_preview_does_not_resolve_credentials_or_send(self):
        with mock.patch.object(sender, "connections") as targets, \
                mock.patch.object(sender.requests, "post") as post, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(sender.main(["--steps", "1"]), 0)
        targets.assert_not_called()
        post.assert_not_called()
        self.assertIn("Preview only: no data sent.", output.getvalue())

    def test_console_counts_pacing_and_payloads(self):
        targets = {eq: ("https://example.invalid", ()) for eq in sender.FIELDS}
        for steps in (17, 50, 100, 120):
            with self.subTest(steps=steps), mock.patch.object(sender, "connections", return_value=targets), \
                    mock.patch.object(sender, "send_measurements", return_value=("200", True)) as send, \
                    mock.patch.object(sender.time, "sleep") as sleep, \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(sender.main(["--send", "--steps", str(steps)]), 0)
            self.assertEqual(send.call_count, steps * 2)
            self.assertEqual(sleep.call_count, steps - 1)
            self.assertTrue(all(call.args == (60,) for call in sleep.call_args_list))
            for call in send.call_args_list:
                payload = call.args[3]
                self.assertEqual(len(payload), 3)
                self.assertTrue(all(isinstance(value, float) for value in payload.values()))
                self.assertFalse(set(payload) & {"timestamp", "time", "epoch"})
            self.assertIn("interval_seconds=60", output.getvalue())
            self.assertIn(f"HTTP-accepted measurement values: {steps * 6}", output.getvalue())
            self.assertIn("request UTC", output.getvalue())

    def test_short_interval_rejected_before_credentials(self):
        with mock.patch.object(sender, "connections") as targets, \
                contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            sender.main(["--send", "--interval", "30"])
        self.assertEqual(error.exception.code, 2)
        targets.assert_not_called()

    def test_timeout_is_sanitized_and_second_failure_is_partial(self):
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / "attempts.csv"
            with mock.patch.object(sender.requests, "post", side_effect=sender.requests.Timeout("private-marker")):
                self.assertEqual(sender.send_measurements(("https://example.invalid", ()), "source", "ahu-01",
                                                         {"field": 1.0}, log), ("NETWORK_ERROR", False))
            self.assertNotIn("private-marker", log.read_text())
        targets = {eq: ("https://example.invalid", ()) for eq in sender.FIELDS}
        with mock.patch.object(sender, "connections", return_value=targets), \
                mock.patch.object(sender, "send_measurements", side_effect=[("200", True), ("404", False)]), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(sender.main(["--send", "--steps", "1"]), 1)
        self.assertIn("Run outcome: incomplete", output.getvalue())
        self.assertIn("HTTP-accepted measurement values: 3", output.getvalue())

"""Exercise replay-session progress without opening widgets or making requests."""

import importlib.util
import base64
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
try:
    import tkinter
except ImportError:
    tkinter = None

import panel_support as support


@unittest.skipIf(tkinter is None, "Optional Tkinter not installed")
class PanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("test_panel_module", ROOT / "scripts/tandem-control-panel.py")
        cls.panel = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.panel)

    def test_partial_failure_resumes_only_pending_equipment(self):
        panel = self.panel
        batches, _ = panel.sender.read_batches(ROOT / "data/demo_hvac.csv")
        session = panel.ReplaySession(batches)
        targets = {equipment: ("https://example.invalid", ()) for equipment in panel.sender.FIELDS}
        reports = []
        with mock.patch.object(panel.sender, "send_measurements", side_effect=[("200", True), ("404", False)]):
            session.run(targets, 1, 60, threading.Event(), reports.append, ROOT / "unused.csv")
        self.assertEqual((session.batch_index, session.equipment_index), (0, 1))
        with mock.patch.object(panel.time, "monotonic", return_value=10**12), \
                mock.patch.object(panel.sender, "send_measurements", return_value=("200", True)) as send:
            session.run(targets, 1, 60, threading.Event(), reports.append, ROOT / "unused.csv")
        self.assertEqual(send.call_count, 1)
        self.assertEqual(send.call_args.args[2], "vav-3")
        self.assertEqual((session.batch_index, session.equipment_index), (1, 0))

    def test_stop_interrupts_cooldown_without_sending(self):
        panel = self.panel
        batches, _ = panel.sender.read_batches(ROOT / "data/demo_hvac.csv")
        session = panel.ReplaySession(batches)
        session.last_attempt["ahu-01"] = 100
        stop = mock.Mock()
        stop.wait.return_value = True
        with mock.patch.object(panel.time, "monotonic", return_value=110), \
                mock.patch.object(panel.sender, "send_measurements") as send:
            session.run({}, 1, 60, stop, lambda message: None, ROOT / "unused.csv")
        stop.wait.assert_called_once_with(50)
        send.assert_not_called()
        self.assertEqual(session.last_run["outcome"], "interrupted")
        self.assertEqual(session.last_run["requests_attempted"], 0)

    def test_run_evidence_complete_failed_and_exception(self):
        panel = self.panel
        batches, _ = panel.sender.read_batches(ROOT / "data/demo_hvac.csv")
        cases = [([("200", True), ("200", True)], "complete", 1, 2),
                 ([("200", True), ("404", False)], "failed", 0, 1)]
        for responses, outcome, complete, accepted in cases:
            session, reports = panel.ReplaySession(batches), []
            with mock.patch.object(panel.sender, "send_measurements", side_effect=responses):
                session.run({eq: None for eq in panel.sender.FIELDS}, 1, 60,
                            threading.Event(), reports.append, ROOT / "unused.csv")
            run = session.last_run
            self.assertEqual((run["outcome"], run["completed_batches"], run["requests_accepted"]),
                             (outcome, complete, accepted))
            self.assertEqual(run["requested_batches"], 1)
            self.assertEqual(run["interval_seconds"], 60)
            self.assertIsNotNone(run["to_utc"])
            self.assertTrue(any("Run started UTC:" in line for line in reports))
            self.assertTrue(any("Run ended UTC:" in line for line in reports))
        session, reports = panel.ReplaySession(batches), []
        with mock.patch.object(panel.sender, "send_measurements", side_effect=OSError("sensitive-fixture")), self.assertRaises(OSError):
            session.run({eq: None for eq in panel.sender.FIELDS}, 1, 60,
                        threading.Event(), reports.append, ROOT / "unused.csv")
        self.assertEqual(session.last_run["outcome"], "failed")
        self.assertNotIn("sensitive-fixture", "\n".join(reports))


class PanelSupportTests(unittest.TestCase):
    def test_session_categories_utc_and_sanitization(self):
        log = support.SessionLog()
        url = "https://" + "user:secret@host/path"
        log.append("PREVIEW", "Numeric payload only")
        log.append("SEND", f"{url} APS_CLIENT_SECRET=private-marker token=private-token\nnext")
        log.append("READBACK", "Six genuine series")
        text = log.text()
        for secret in (url, "private-marker", "private-token"):
            self.assertNotIn(secret, text)
        self.assertIn("GUI session log (not captured terminal stdout)", text)
        self.assertIn("Z [PREVIEW]", text)
        self.assertIn("Z [SEND]", text)
        self.assertIn("Z [READBACK]", text)
        with self.assertRaises(ValueError):
            log.append("unknown", "not accepted")

    def test_save_preserves_existing_and_replaces_only_explicitly(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "session.txt"
            support.save_session_log(path, "first")
            with self.assertRaises(FileExistsError):
                support.save_session_log(path, "second")
            self.assertEqual(path.read_text(), "first")
            with mock.patch.object(Path, "replace", side_effect=OSError("fixture")), self.assertRaises(OSError):
                support.save_session_log(path, "second", replace=True)
            self.assertEqual(path.read_text(), "first")
            self.assertEqual(list(Path(folder).iterdir()), [path])
            support.save_session_log(path, "second", replace=True)
            self.assertEqual(path.read_text(), "second")

    def test_failed_new_session_write_removes_only_new_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "failed.txt"
            original = Path.open
            class BrokenWrite:
                def __enter__(self):
                    self.file = original(path, "x")
                    self.file.write("partial")
                    return self
                def write(self, text):
                    raise OSError("fixture")
                def __exit__(self, *args):
                    self.file.close()
            with mock.patch.object(Path, "open", return_value=BrokenWrite()), self.assertRaises(OSError):
                support.save_session_log(path, "content")
            self.assertFalse(path.exists())

    def test_utc_padding_crosses_midnight_without_mutating_original(self):
        run = {"from_utc": "2026-11-05T23:59:59.900Z", "to_utc": "2026-11-06T00:00:00.100Z"}
        original = dict(run)
        self.assertEqual(support.suggested_bounds(run),
                         ("2026-11-05T23:58:59.900Z", "2026-11-06T00:01:00.100Z"))
        self.assertEqual(run, original)
        for padding in (-1, float("nan"), True):
            with self.assertRaises(ValueError):
                support.suggested_bounds(run, padding)

    def test_open_uses_os_association_and_folder_without_shell(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "a file.csv"
            path.write_text("fixture")
            with mock.patch.object(support.sys, "platform", "win32"), mock.patch.object(support.os, "startfile", create=True) as launch:
                support.open_result(path)
                launch.assert_called_once_with(str(path.resolve()))
                support.open_result(path, folder=True)
                self.assertEqual(launch.call_args.args, (str(path.resolve().parent),))
            for platform, command in (("darwin", "open"), ("linux", "xdg-open")):
                with mock.patch.object(support.sys, "platform", platform), mock.patch.object(support.subprocess, "run") as launch:
                    support.open_result(path)
                    launch.assert_called_once_with([command, str(path.resolve())], check=True, capture_output=True, timeout=5)
                with mock.patch.object(support.sys, "platform", platform), \
                        mock.patch.object(support.subprocess, "run", side_effect=support.subprocess.CalledProcessError(1, command, output="private-fixture")), \
                        self.assertRaises(OSError) as error:
                    support.open_result(path)
                self.assertNotIn("private-fixture", str(error.exception))
            with self.assertRaises(OSError):
                support.open_result(Path(folder) / "missing.csv")


class Value:
    def __init__(self, value=""):
        self.value = value
    def get(self):
        return self.value
    def set(self, value):
        self.value = value


class Widget:
    def __init__(self):
        self.state = "normal"
    def configure(self, **values):
        self.state = values["state"]


@unittest.skipIf(tkinter is None, "Optional Tkinter not installed")
class PanelFeatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("feature_panel", ROOT / "scripts/tandem-control-panel.py")
        cls.panel = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.panel)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        (self.folder / "config").mkdir()
        self.output_path = self.folder / "outputs" / "result.csv"
        panel = self.panel
        self.patches = [mock.patch.object(panel, "ROOT", self.folder),
                        mock.patch.object(panel, "messagebox"),
                        mock.patch.object(panel, "read_credentials", return_value={"APS_CLIENT_ID": "synthetic-id", "APS_CLIENT_SECRET": "synthetic-secret"}),
                        mock.patch.object(panel.filedialog, "asksaveasfilename", return_value=str(self.output_path))]
        for patcher in self.patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.app = panel.ControlPanel.__new__(panel.ControlPanel)
        app = self.app
        app.root = mock.Mock()
        app.events = panel.queue.Queue()
        app.stop = threading.Event()
        app.worker = None
        app.operation = None
        app.closing = False
        app.evidence = support.SessionLog()
        app.result_path = None
        app.last_sender_bounds = None
        app.result_note, app.bounds_note, app.status = Value(), Value(), Value()
        app.from_utc, app.to_utc = Value("2026-11-05T19:00:00.000Z"), Value("2026-11-05T19:10:00.000Z")
        app.output = mock.Mock()
        app.inputs, app.read_inputs = [Widget()], [Widget(), Widget()]
        for name in ("preview_button", "one_button", "start_button", "stop_button", "suggest_button",
                     "export_button", "save_button", "open_csv_button", "open_folder_button"):
            setattr(app, name, Widget())
        batches, _ = panel.sender.read_batches(ROOT / "data/demo_hvac.csv")
        app.session = panel.ReplaySession(batches)
        app.interval, app.count = Value("60"), Value("1")
        self.config = {"facility_urn": "urn:adsk.dtt:fixture", "connections": {}}
        app.urls = {}
        for number, (equipment, fields) in enumerate(panel.sender.FIELDS.items(), 1):
            key = base64.urlsafe_b64encode(bytes([number]) * 20).decode().rstrip("=")
            self.config["connections"][equipment] = {"connection_key": key,
                "parameters": {field: f"z:{number}_{index}" for index, field in enumerate(fields.values())}}
            app.urls[equipment] = Value("https://" + "user:" + "synthetic" + "@tandem.autodesk.com/api/v1/timeseries/models/urn:adsk.dtm:fixture/streams/" + key)
        self.save_config()
        self.summary = {"total_measurements": 6, "empty_series": [],
                        "counts": {eq + "/" + field: 1 for eq, fields in panel.sender.FIELDS.items() for field in fields.values()}}
        self.rows = [{"equipment_id": eq, "field": field, "value": 42.5}
                     for eq, fields in panel.sender.FIELDS.items() for field in fields.values()]
        app.set_busy(None)

    def save_config(self):
        (self.folder / "config/readback.json").write_text(json.dumps(self.config))

    def finish_worker(self):
        self.app.worker.join(timeout=3)
        self.assertFalse(self.app.worker.is_alive())
        self.app.poll()

    def test_correspondence_accepts_short_full_and_rejects_swapped_models_or_paths(self):
        targets = {eq: self.panel.sender.destination(var.get()) for eq, var in self.app.urls.items()}
        config = self.panel.exporter.load_config(self.folder / "config/readback.json")
        support.verify_correspondence(config, targets)
        original = self.config["facility_urn"]
        self.config["facility_urn"] = "urn:adsk.dtt:other"
        with self.assertRaises(ValueError):
            support.verify_correspondence(self.config, targets)
        self.config["facility_urn"] = original
        a, b = self.config["connections"]
        self.config["connections"][a]["connection_key"], self.config["connections"][b]["connection_key"] = (
            self.config["connections"][b]["connection_key"], self.config["connections"][a]["connection_key"])
        with self.assertRaises(ValueError):
            support.verify_correspondence(self.config, targets)
        bad = {eq: ("https://example.invalid/unknown", ()) for eq in targets}
        with self.assertRaises(ValueError):
            support.verify_correspondence(config, bad)

    def test_success_background_states_counts_and_no_automatic_open(self):
        panel, app = self.panel, self.app
        with mock.patch.object(panel.exporter, "TandemReader") as reader, \
                mock.patch.object(panel.exporter, "collect", return_value=(self.rows, self.summary)) as collect, \
                mock.patch.object(support, "open_result") as launch, \
                mock.patch.object(panel.sender, "send_measurements") as send:
            app.export_readings()
            self.assertEqual(app.operation, "export")
            self.assertEqual(app.export_button.state, "disabled")
            self.assertEqual(app.start_button.state, "disabled")
            self.assertEqual(app.stop_button.state, "disabled")
            self.assertEqual(app.open_csv_button.state, "disabled")
            app.start(True)  # Even a direct callback cannot send during export.
            self.finish_worker()
            collect.assert_called_once()
            self.assertEqual(collect.call_args.args[2:], (
                panel.exporter.utc_bound(app.from_utc.get()), panel.exporter.utc_bound(app.to_utc.get())))
            reader.return_value.close.assert_called_once()
            launch.assert_not_called()
            send.assert_not_called()
        self.assertEqual(app.result_path, self.output_path)
        self.assertTrue(self.output_path.is_file())
        self.assertTrue(self.output_path.with_suffix(".csv.summary.json").is_file())
        self.assertEqual(app.export_button.state, "normal")
        self.assertEqual(app.open_csv_button.state, "normal")
        self.assertEqual(app.evidence.text().count("1 stored measurements"), 6)
        dialog = panel.filedialog.asksaveasfilename.call_args.kwargs
        self.assertEqual(dialog["initialdir"], str(self.folder / "outputs"))
        self.assertTrue(dialog["initialfile"].startswith("readback-"))

    def test_empty_and_partial_results_are_explicit(self):
        for partial in (False, True):
            with self.subTest(partial=partial):
                counts = {key: (1 if partial and index == 0 else 0) for index, key in enumerate(self.summary["counts"])}
                summary = {"counts": counts, "total_measurements": sum(counts.values()),
                           "empty_series": [key for key, count in counts.items() if not count]}
                self.output_path = self.folder / "outputs" / f"empty-{partial}.csv"
                self.panel.filedialog.asksaveasfilename.return_value = str(self.output_path)
                with mock.patch.object(self.panel.exporter, "TandemReader"), \
                        mock.patch.object(self.panel.exporter, "collect", return_value=(self.rows[:sum(counts.values())], summary)):
                    self.app.export_readings()
                    self.finish_worker()
                self.assertIn("Partial export" if partial else "EMPTY export", self.app.result_note.get())
                self.assertIn("0 stored measurements (EMPTY)", self.app.evidence.text())

    def test_failures_invalidate_stale_buttons_and_hide_sensitive_details(self):
        for failure in (self.panel.ApiError("APS authentication: HTTP 401."), OSError("sensitive-fixture"), ValueError("sensitive-fixture")):
            with self.subTest(failure=type(failure).__name__):
                self.app.result_path = self.folder / "earlier.csv"
                with mock.patch.object(self.panel.exporter, "TandemReader"), \
                        mock.patch.object(self.panel.exporter, "collect", side_effect=failure):
                    self.app.export_readings()
                    self.finish_worker()
                self.assertIsNone(self.app.result_path)
                self.assertEqual(self.app.open_csv_button.state, "disabled")
                self.assertEqual(self.app.start_button.state, "normal")
                self.assertNotIn("sensitive-fixture", self.app.evidence.text())
                self.assertFalse(self.output_path.exists())
        self.assertIn("HTTP 401", self.app.evidence.text())

    def test_missing_credentials_config_and_mismatched_urls_never_query(self):
        app, panel = self.app, self.panel
        for mode in ("credentials", "config", "urls"):
            with self.subTest(mode=mode), mock.patch.object(panel.exporter, "TandemReader") as reader:
                self.save_config()
                panel.read_credentials.return_value = {"APS_CLIENT_ID": "id", "APS_CLIENT_SECRET": "synthetic"}
                if mode == "credentials":
                    panel.read_credentials.return_value = {"APS_CLIENT_ID": "", "APS_CLIENT_SECRET": ""}
                elif mode == "config":
                    (self.folder / "config/readback.json").unlink()
                else:
                    app.urls["ahu-01"].set(app.urls["ahu-01"].get().replace("urn:adsk.dtm:fixture", "urn:adsk.dtm:other"))
                app.export_readings()
                reader.assert_not_called()
                self.assertIsNone(app.worker)
        self.assertIn("docs/READBACK.md", app.evidence.text())

    def test_invalid_ranges_cancel_and_csv_or_summary_collision_preserve_files(self):
        app, panel = self.app, self.panel
        with mock.patch.object(panel.exporter, "TandemReader") as reader:
            for start, end in (("2026-11-05T19:00:00", "2026-11-05T19:10:00Z"),
                               ("2026-11-05T19:10:00Z", "2026-11-05T19:00:00Z")):
                app.from_utc.set(start)
                app.to_utc.set(end)
                app.export_readings()
            app.from_utc.set("2026-11-05T19:00:00Z")
            app.to_utc.set("2026-11-05T19:10:00Z")
            panel.filedialog.asksaveasfilename.return_value = ""
            app.export_readings()
            panel.filedialog.asksaveasfilename.return_value = str(self.output_path)
            self.output_path.parent.mkdir(exist_ok=True)
            for path in (self.output_path, self.output_path.with_suffix(".csv.summary.json")):
                path.write_text("preserve")
                app.export_readings()
                self.assertEqual(path.read_text(), "preserve")
                path.unlink()
            reader.assert_not_called()

    def test_output_write_failure_restores_controls_and_preserves_earlier_file(self):
        self.output_path.parent.mkdir()
        earlier = self.output_path.parent / "earlier.csv"
        earlier.write_text("preserve")
        with mock.patch.object(self.panel.exporter, "TandemReader"), \
                mock.patch.object(self.panel.exporter, "collect", return_value=(self.rows, self.summary)), \
                mock.patch.object(self.panel.exporter, "write_export", side_effect=OSError("sensitive-path")):
            self.app.export_readings()
            self.finish_worker()
        self.assertIsNone(self.app.result_path)
        self.assertEqual(earlier.read_text(), "preserve")
        self.assertNotIn("sensitive-path", self.app.evidence.text())

    def test_racing_csv_collision_does_not_present_an_earlier_file_as_success(self):
        def arriving_file(*args):
            self.output_path.write_text("another export won")
            return self.rows, self.summary
        with mock.patch.object(self.panel.exporter, "TandemReader"), \
                mock.patch.object(self.panel.exporter, "collect", side_effect=arriving_file):
            self.app.export_readings()
            self.finish_worker()
        self.assertEqual(self.output_path.read_text(), "another export won")
        self.assertIsNone(self.app.result_path)
        self.assertEqual(self.app.open_csv_button.state, "disabled")
        self.assertFalse(self.output_path.with_suffix(".csv.summary.json").exists())

    def test_save_dialog_replacement_confirmation_and_preview_categories(self):
        app, panel = self.app, self.panel
        path = self.folder / "gui-session.txt"
        panel.filedialog.asksaveasfilename.return_value = str(path)
        app.preview()
        app.save_log()
        original = path.read_text()
        self.assertIn("[PREVIEW]", original)
        self.assertIn("GUI session log", original)
        self.assertNotIn("synthetic-secret", original)
        panel.messagebox.askyesno.return_value = False
        app.save_log()
        self.assertEqual(path.read_text(), original)
        panel.messagebox.askyesno.return_value = True
        app.save_log()
        self.assertNotEqual(path.read_text(), original)

    def test_open_is_explicit_and_failure_keeps_saved_result(self):
        self.output_path.parent.mkdir()
        self.output_path.write_text("fixture")
        app = self.app
        app.result_path = self.output_path
        with mock.patch.object(support, "open_result") as launch:
            app.open_saved(False)
            app.open_saved(True)
            self.assertEqual(launch.call_args_list, [mock.call(self.output_path, folder=False), mock.call(self.output_path, folder=True)])
        with mock.patch.object(support, "open_result", side_effect=OSError("sensitive-association")):
            app.open_saved(False)
        self.assertEqual(app.result_path, self.output_path)
        self.assertEqual(self.output_path.read_text(), "fixture")
        self.assertNotIn("sensitive-association", app.evidence.text())

    def test_send_completion_preserves_original_bounds_and_suggests_padding(self):
        app = self.app
        with mock.patch.object(self.panel.sender, "send_measurements", return_value=("200", True)):
            app.start(True)
            self.assertEqual(app.operation, "send")
            self.assertEqual(app.export_button.state, "disabled")
            self.finish_worker()
        run = app.session.last_run
        self.assertEqual(app.last_sender_bounds, {"from_utc": run["from_utc"], "to_utc": run["to_utc"]})
        self.assertEqual((app.from_utc.get(), app.to_utc.get()), support.suggested_bounds(run))
        self.assertIn("not padded", app.bounds_note.get())
        self.assertIn("requested/completed batches 1/1", app.evidence.text())
        self.assertIn("[SEND]", app.evidence.text())

    def test_streaming_blocks_export_and_closing_waits_for_worker(self):
        app = self.app
        app.set_busy("send")
        with mock.patch.object(self.panel.exporter, "TandemReader") as reader:
            app.export_readings()
            reader.assert_not_called()
        app.worker = mock.Mock()
        app.worker.is_alive.return_value = True
        app.set_busy("export")
        app.close()
        app.root.destroy.assert_not_called()
        self.assertEqual(app.export_button.state, "disabled")
        app.worker.is_alive.return_value = False
        app.events.put(("finished", "export"))
        app.poll()
        app.root.destroy.assert_called_once()

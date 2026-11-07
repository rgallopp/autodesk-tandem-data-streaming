"""Optional Tkinter interface, launched on Windows by Open-Tandem-Controls.cmd.

Opening/previewing sends nothing. Live buttons reuse the CLI sender. Explicit
historical exports reuse the reader; settings and progress last only in this window.
"""

import importlib.util
import math
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

import panel_support as support
import read_readings as exporter
from tandem_api import ApiError, read_credentials

# Load the hyphenated sender filename to share validation and sending, not duplicate it.
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "hvac_sender", ROOT / "scripts" / "ingest-data-individual-stream-from-csv.py")
sender = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sender)


def load_panel_urls(path):
    """Load private file URLs only; missing values can be entered in masked widgets.

    Unlike the CLI, this does not consult URL environment variables. Edits in the
    panel never update the file, and APS readback credentials are unrelated.
    """
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig") as source:
        values = sender.json.load(source)
    if not isinstance(values, dict):
        raise ValueError("Expected a configuration object.")
    urls = {}
    for equipment in sender.FIELDS:
        url = values.get(equipment, "")
        if not isinstance(url, str):
            raise ValueError("Expected URL text.")
        if url:
            sender.destination(url)
        urls[equipment] = url
    endpoints = [sender.destination(url)[0] for url in urls.values() if url]
    if len(endpoints) != len(set(endpoints)):
        raise ValueError("Connections must be distinct.")
    return urls


class ReplaySession:
    """Session progress and cooldowns, independent of the desktop widgets."""

    def __init__(self, batches):
        # Track progress in memory, including the pending equipment within a batch.
        # Reopening the panel starts a new session from the beginning.
        self.batches = batches
        self.batch_index = 0
        self.equipment_index = 0
        self.last_attempt = {}
        self.last_run = None

    def run(self, targets, count, interval, stop, report, log_path):
        """Resume pending equipment, with interruptible per-connection cooldowns."""
        equipment_ids = list(sender.FIELDS)
        end = self.batch_index + count
        run = self.last_run = {
            "from_utc": support.utc_now(), "to_utc": None, "interval_seconds": interval,
            "requested_batches": count, "completed_batches": 0,
            "requests_attempted": 0, "requests_accepted": 0, "accepted_values": 0,
            "outcome": "interrupted", "first_batch": self.batch_index + 1,
            "first_equipment": equipment_ids[self.equipment_index],
        }
        report(f"Run started UTC: {run['from_utc']}; interval {interval:g} seconds; "
               f"requested batches {count}; first batch {run['first_batch']}, {run['first_equipment']}.")
        try:
            while self.batch_index < end:
                stamp, group = self.batches[self.batch_index]
                while self.equipment_index < len(equipment_ids):
                    equipment = equipment_ids[self.equipment_index]
                    # Per-connection monotonic cooldowns survive Stop/Start in this session.
                    remaining = self.last_attempt.get(equipment, -math.inf) + interval - time.monotonic()
                    if remaining > 0:
                        report(f"Waiting {math.ceil(remaining)} seconds before {equipment}.")
                        if stop.wait(remaining):
                            return
                    if stop.is_set():
                        return
                    report(f"Request UTC {support.utc_now()}; batch {self.batch_index + 1}, "
                           f"{equipment}; source {stamp} (not posted); values {len(group[equipment])}.")
                    run["requests_attempted"] += 1
                    try:
                        status, success = sender.send_measurements(
                            targets[equipment], stamp, equipment, group[equipment], log_path)
                    finally:
                        # Even failed attempts can have reached Tandem.
                        self.last_attempt[equipment] = time.monotonic()
                    report(f"{equipment}: {status}")
                    if not success:
                        run["outcome"] = "failed"
                        report("Stopped on failure. Delivery may be uncertain; check history/logs before retrying.")
                        return
                    run["requests_accepted"] += 1
                    run["accepted_values"] += len(group[equipment])
                    # Advance only after acceptance; failed payloads remain pending.
                    self.equipment_index += 1
                self.batch_index += 1
                self.equipment_index = 0
                run["completed_batches"] += 1
                report(f"Batch {self.batch_index} complete. Verify stored history through API readback and charts.")
            run["outcome"] = "complete"
        except Exception:
            run["outcome"] = "failed"
            raise
        finally:
            run["to_utc"] = support.utc_now()
            report(f"Run ended UTC: {run['to_utc']}; status {run['outcome']}; "
                   f"requested/completed batches {count}/{run['completed_batches']}; "
                   f"HTTP-accepted/attempted requests {run['requests_accepted']}/{run['requests_attempted']}; "
                   f"HTTP-accepted values {run['accepted_values']}. This is not confirmed storage.")


class ControlPanel:
    def __init__(self, root):
        self.root = root
        self.root.title("autodesk-tandem-data-streaming")
        self.root.geometry("980x900")
        self.root.minsize(850, 760)
        # Background work reports through a thread-safe queue. The stop event
        # cancels waits; an active HTTP request finishes before stopping.
        self.events = queue.Queue()
        self.stop = threading.Event()
        self.worker = None
        self.operation = None
        self.closing = False
        self.evidence = support.SessionLog()
        self.last_sender_bounds = None
        self.result_path = None
        # Validate the dataset at startup without sending any measurements.
        batches, skipped = sender.read_batches(ROOT / "data" / "demo_hvac.csv")
        self.session = ReplaySession(batches)

        frame = ttk.Frame(root, padding=14)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="autodesk-tandem-data-streaming", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(frame, text="Opening and preview send nothing. Send buttons write measurements; export reads history.").pack(anchor="w", pady=(4, 10))

        # Load optional configuration and create masked URL fields. Edits stay
        # in memory; the panel does not save them back to config.json.
        self.inputs = []
        self.urls = {}
        config_error = False
        try:
            configured_urls = load_panel_urls(ROOT / "config" / "config.json")
        except (ValueError, OSError):
            configured_urls = {}
            config_error = True
        for equipment in sender.FIELDS:
            label = f"{equipment} ingestion URL"
            ttk.Label(frame, text=label).pack(anchor="w")
            variable = tk.StringVar(value=configured_urls.get(equipment, ""))
            entry = ttk.Entry(frame, textvariable=variable, show="*")
            entry.pack(fill="x", pady=(3, 6))
            self.urls[equipment] = variable
            self.inputs.append(entry)
        ttk.Label(frame, text="Loads private config.json on opening. Edits here stay in memory; URLs are hidden.").pack(anchor="w")

        options = ttk.Frame(frame)
        options.pack(fill="x", pady=8)
        ttk.Label(options, text="Interval (seconds, minimum 60)").grid(row=0, column=0, sticky="w")
        self.interval = tk.StringVar(value="60")
        interval_entry = ttk.Entry(options, textvariable=self.interval, width=10)
        interval_entry.grid(row=1, column=0, sticky="w", pady=4)
        ttk.Label(options, text="Batches for Start streaming").grid(row=0, column=1, padx=25, sticky="w")
        self.count = tk.StringVar(value="6")
        count_entry = ttk.Entry(options, textvariable=self.count, width=10)
        count_entry.grid(row=1, column=1, padx=25, sticky="w")
        self.inputs.extend([interval_entry, count_entry])

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(0, 12))
        self.preview_button = ttk.Button(buttons, text="Preview next batch", command=self.preview)
        self.one_button = ttk.Button(buttons, text="Send one batch", command=lambda: self.start(True))
        self.start_button = ttk.Button(buttons, text="Start streaming", command=lambda: self.start(False))
        self.stop_button = ttk.Button(buttons, text="Stop", command=self.request_stop, state="disabled")
        for button in (self.preview_button, self.one_button, self.start_button, self.stop_button):
            button.pack(side="left", padx=(0, 10))

        self.status = tk.StringVar()
        ttk.Label(frame, textvariable=self.status, font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=5)
        ttk.Label(frame, text="Stop cancels the wait or stops after the current request. Successful requests cannot be undone.", wraplength=810).pack(anchor="w", pady=(0, 10))

        history = ttk.LabelFrame(frame, text="Genuine API history (read-only; no new send required)", padding=10)
        history.pack(fill="x", pady=(0, 8))
        self.from_utc = tk.StringVar()
        self.to_utc = tk.StringVar()
        self.bounds_note = tk.StringVar(value="Original sender UTC bounds: none in this session. Enter a known historical interval.")
        ttk.Label(history, textvariable=self.bounds_note, wraplength=880).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(history, text="From UTC (inclusive)").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Label(history, text="To UTC (exclusive)").grid(row=1, column=1, sticky="w", padx=12, pady=(6, 0))
        from_entry = ttk.Entry(history, textvariable=self.from_utc, width=32)
        from_entry.grid(row=2, column=0, sticky="ew", pady=4)
        to_entry = ttk.Entry(history, textvariable=self.to_utc, width=32)
        to_entry.grid(row=2, column=1, sticky="ew", padx=12, pady=4)
        self.export_button = ttk.Button(history, text="Export readings", command=self.export_readings)
        self.export_button.grid(row=2, column=2, sticky="e")
        self.suggest_button = ttk.Button(history, text="Use last run ±60s", command=self.use_last_bounds, state="disabled")
        self.suggest_button.grid(row=3, column=0, sticky="w")
        ttk.Label(history, text="Suggestion adds 60s on each side for timing differences; edit for actual collection.\nUses private .env + config/readback.json; checks these against the panel URLs.", wraplength=640).grid(row=3, column=1, columnspan=2, sticky="w", padx=12)
        history.columnconfigure(0, weight=1)
        history.columnconfigure(1, weight=1)
        self.read_inputs = [from_entry, to_entry]

        self.output = scrolledtext.ScrolledText(frame, height=9, wrap="word", state="disabled")
        self.output.pack(fill="both", expand=True)
        ttk.Label(frame, text="Results append to logs/hvac_send_log.csv. HTTP success still needs verification in Tandem.", wraplength=810).pack(anchor="w", pady=(10, 0))
        files = ttk.Frame(frame)
        files.pack(fill="x", pady=(8, 0))
        self.save_button = ttk.Button(files, text="Save session log", command=self.save_log)
        self.save_button.pack(side="left")
        self.open_csv_button = ttk.Button(files, text="Open CSV", command=lambda: self.open_saved(False), state="disabled")
        self.open_csv_button.pack(side="left", padx=10)
        self.open_folder_button = ttk.Button(files, text="Open folder", command=lambda: self.open_saved(True), state="disabled")
        self.open_folder_button.pack(side="left")
        self.result_note = tk.StringVar(value="No API export saved in this session.")
        ttk.Label(frame, textvariable=self.result_note, wraplength=920).pack(anchor="w", pady=(6, 0))
        self.write(f"Loaded {len(batches)} complete batches; skipped {skipped} incomplete timestamps.")
        if config_error:
            self.write("Could not load config.json. Check its JSON and URL formats, or paste URLs into the fields.")
        elif any(configured_urls.values()):
            self.write("Loaded connection URL(s) from private config.json into masked fields. No requests sent.")
        else:
            self.write("No requests sent. Paste the two individual connection URLs to begin.")
        self.write("Progress and cooldowns last only while this window is open. Do not run a second sender alongside it.")
        self.refresh_status()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(100, self.poll)

    def write(self, message, category="INFO"):
        """The GUI and saved session log share the same sanitized UTC messages."""
        line = self.evidence.append(category, message)
        self.output.configure(state="normal")
        self.output.insert("end", line + "\n")
        self.output.see("end")
        self.output.configure(state="disabled")

    def refresh_status(self):
        session = self.session
        if session.batch_index == len(session.batches):
            self.status.set("End of CSV. Close and reopen to replay from the beginning.")
        else:
            pending = list(sender.FIELDS)[session.equipment_index]
            self.status.set(f"Next: batch {session.batch_index + 1}/{len(session.batches)}, {pending}")

    def preview(self):
        """Inspect only pending equipment without advancing session progress."""
        if self.session.batch_index == len(self.session.batches):
            self.write("No batches remain in this session.", "PREVIEW")
            return
        stamp, group = self.session.batches[self.session.batch_index]
        self.write(f"Preview source {stamp}; not sent, no outgoing timestamps.", "PREVIEW")
        for equipment in list(sender.FIELDS)[self.session.equipment_index:]:
            self.write(f"{equipment}: {sender.json.dumps(group[equipment], sort_keys=True)}", "PREVIEW")

    def start(self, single):
        if self.operation or self.closing or (self.worker and self.worker.is_alive()):
            return
        try:
            interval = float(self.interval.get())
            count = 1 if single else int(self.count.get())
            remaining = len(self.session.batches) - self.session.batch_index
            if not math.isfinite(interval) or interval < 60:
                raise ValueError("Choose an interval of at least 60 seconds.")
            if count < 1 or count > remaining:
                raise ValueError(f"Choose between 1 and {remaining} batches remaining in this session.")
        except ValueError as error:
            # User inputs here are numbers only, never URL values.
            messagebox.showerror("Check run settings", str(error))
            return
        try:
            targets = {equipment: sender.destination(variable.get()) for equipment, variable in self.urls.items()}
            if len({target[0] for target in targets.values()}) != len(targets):
                raise ValueError()
        except ValueError:
            messagebox.showerror("Check connection URLs", "Paste two valid, distinct individual Tandem ingestion URLs.")
            return
        self.stop.clear()
        self.set_busy("send")
        self.write(f"Starting {count} batch(es), interval {interval:g} seconds. Existing session cooldowns apply.", "SEND")

        # Keep network requests and cooldown waits outside the GUI thread.
        def work():
            try:
                self.session.run(targets, count, interval, self.stop,
                                 lambda text: self.events.put(("message", "SEND", text)),
                                 ROOT / "logs" / "hvac_send_log.csv")
            except Exception:
                self.events.put(("message", "SEND", "Failed: check file access and the attempt log; delivery may be uncertain. Sensitive error details are hidden."))
            finally:
                self.events.put(("finished", "send"))

        # A non-daemon thread allows an active request to finish logging before exit.
        self.worker = threading.Thread(target=work, daemon=False)
        self.worker.start()

    def set_busy(self, operation):
        """One worker owns a snapshot of settings; widgets remain on the GUI thread."""
        self.operation = operation
        disabled = operation is not None or self.closing
        for widget in self.inputs + self.read_inputs + [
                self.preview_button, self.one_button, self.start_button,
                self.export_button, self.save_button]:
            widget.configure(state="disabled" if disabled else "normal")
        self.stop_button.configure(state="normal" if operation == "send" and not self.closing else "disabled")
        self.suggest_button.configure(state="normal" if self.last_sender_bounds and not disabled else "disabled")
        available = self.result_path is not None and not disabled
        self.open_csv_button.configure(state="normal" if available else "disabled")
        self.open_folder_button.configure(state="normal" if available else "disabled")

    def use_last_bounds(self):
        if self.last_sender_bounds:
            start, end = support.suggested_bounds(self.last_sender_bounds)
            self.from_utc.set(start)
            self.to_utc.set(end)
            self.write(f"Suggested query UTC [{start}, {end}); padding 60 seconds each side. "
                       "Original sender bounds preserved; the window may include other runs.", "READBACK")

    def save_log(self):
        if self.operation or self.closing:
            return
        try:
            (ROOT / "outputs").mkdir(exist_ok=True)
            selected = filedialog.asksaveasfilename(
                parent=self.root, title="Save GUI session log (not terminal stdout)",
                initialdir=str(ROOT / "outputs"),
                initialfile=f"gui-session-{support.filename_time()}.txt",
                defaultextension=".txt", filetypes=[("Text log", "*.txt")], confirmoverwrite=False)
            if not selected:
                return
            path = Path(selected)
            replace = path.exists()
            if replace and not messagebox.askyesno(
                    "Replace session log?", "This file exists. Replace it with this GUI session log?", parent=self.root):
                return
            support.save_session_log(path, self.evidence.text(), replace=replace)
            self.write(f"GUI session log saved: {path}", "FILE")
        except (OSError, ValueError):
            self.write("Could not save the GUI session log. Existing files are preserved; choose a writable new path.", "FILE")
            messagebox.showerror("Session log not saved", "Check the destination and file access; sensitive error details are hidden.", parent=self.root)

    def export_readings(self):
        """Validate locally before starting the existing reader in a worker thread."""
        if self.operation or self.closing or (self.worker and self.worker.is_alive()):
            return
        # Clear associations on every attempt, including validation/dialog failures.
        # Previous files stay on disk but cannot masquerade as this operation's result.
        self.result_path = None
        self.result_note.set("No result from this export attempt.")
        self.set_busy(None)
        try:
            start, end = exporter.utc_bound(self.from_utc.get()), exporter.utc_bound(self.to_utc.get())
            if start >= end:
                raise ValueError()
        except ValueError:
            self.write("Export not started: enter increasing timezone-aware UTC bounds with at most millisecond precision.", "READBACK")
            messagebox.showerror("Check UTC range", "Use From < To, for example 2026-11-05T19:00:00.000Z. From is included; To is excluded.", parent=self.root)
            return
        try:
            targets = {equipment: sender.destination(variable.get()) for equipment, variable in self.urls.items()}
            config = exporter.load_config(ROOT / "config" / "readback.json")
            support.verify_correspondence(config, targets)
            credentials = read_credentials()
            if not all(credentials.values()):
                raise ValueError()
        except (OSError, ValueError, ApiError):
            self.write("Export not started: missing, invalid, or mismatched private configuration. "
                       "Check panel URLs, root .env, and config/readback.json against discovery. See docs/READBACK.md.", "READBACK")
            messagebox.showerror("Check readback setup", "Readback must target the same equipment connections as the panel URLs. "
                                 "Fill APS credentials in root .env and discovered IDs in config/readback.json. "
                                 "See docs/READBACK.md; no requests were made.", parent=self.root)
            return
        try:
            (ROOT / "outputs").mkdir(exist_ok=True)
            selected = filedialog.asksaveasfilename(
                parent=self.root, title="Save genuine API readings (CSV + summary; new files only)",
                initialdir=str(ROOT / "outputs"),
                initialfile=f"readback-{support.filename_time()}.csv",
                defaultextension=".csv", filetypes=[("CSV", "*.csv")], confirmoverwrite=False)
            if not selected:
                self.write("Export canceled before API requests.", "READBACK")
                return
            path = Path(selected)
            if path.exists() or path.with_suffix(path.suffix + ".summary.json").exists():
                self.write("Export not started: CSV or companion summary exists. Choose a new filename; neither is replaced.", "READBACK")
                messagebox.showerror("Choose new output files", "The CSV or its companion summary already exists. Choose another filename.", parent=self.root)
                return
        except OSError:
            self.write("Export not started: cannot prepare the output destination. Check file access.", "READBACK")
            return
        self.write(f"Export started UTC: {support.utc_now()}; query [{exporter.utc_text(start)}, "
                   f"{exporter.utc_text(end)}); panel/readback destinations match. No measurements sent.", "READBACK")
        self.set_busy("export")

        def work():
            reader = None
            try:
                reader = exporter.TandemReader()
                rows, summary = exporter.collect(reader, config, start, end)
                exporter.write_export(path, rows, summary)
                self.events.put(("export_complete", path, summary))
            except ApiError as error:
                self.events.put(("message", "READBACK", f"Export failed: {error}"))
            except (OSError, ValueError):
                self.events.put(("message", "READBACK", "Export failed: check saved mappings, IDs, and fresh writable CSV/summary paths. "
                                 "See docs/READBACK.md. No complete export is assumed; sensitive details are hidden."))
            except Exception:
                self.events.put(("message", "READBACK", "Export failed unexpectedly; no complete result is assumed. Sensitive error details are hidden."))
            finally:
                try:
                    if reader is not None:
                        reader.close()
                finally:
                    self.events.put(("finished", "export"))

        self.worker = threading.Thread(target=work, daemon=False)
        self.worker.start()

    def open_saved(self, folder):
        if self.operation or self.closing or self.result_path is None:
            return
        try:
            support.open_result(self.result_path, folder=folder)
            self.write("Open folder requested." if folder else "Open CSV requested using the OS default application.", "FILE")
        except (OSError, ValueError):
            self.write("Could not open the result. The export is still saved; use its displayed path manually.", "FILE")
            messagebox.showerror("Could not open result", "Check the saved path and your OS file association. The export was not changed.", parent=self.root)

    def request_stop(self):
        self.stop.set()
        self.stop_button.configure(state="disabled")
        self.write("Stop requested. Waiting for any active request to finish; no further requests will start.", "SEND")

    def close(self):
        """Wait for active sending/logging or historical export before window exit."""
        self.closing = True
        self.stop.set()
        if self.worker and self.worker.is_alive():
            self.set_busy(self.operation)
            self.write("Closing after the background operation finishes. Active sends finish logging; exports finish or report failure.")
        else:
            self.root.destroy()

    def poll(self):
        """Only the GUI thread touches widgets; the worker reports via a queue."""
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == "finished":
                    if event[1] == "send" and self.session.last_run is not None:
                        run = self.session.last_run
                        self.last_sender_bounds = {"from_utc": run["from_utc"], "to_utc": run["to_utc"]}
                        self.bounds_note.set(f"Original sender UTC bounds: {run['from_utc']} to {run['to_utc']} "
                                             f"({run['outcome']}; not padded).")
                        self.use_last_bounds()
                    elif event[1] == "export" and self.result_path is None:
                        self.result_note.set("Export failed; no new result. Earlier files remain preserved.")
                    self.set_busy(None)
                    self.refresh_status()
                elif event[0] == "export_complete":
                    self.result_path, summary = event[1:]
                    label = "EMPTY export" if summary["total_measurements"] == 0 else (
                        "Partial export (empty series)" if summary["empty_series"] else "Export complete")
                    self.result_note.set(f"{label}: {self.result_path} ({summary['total_measurements']} API rows; companion summary saved).")
                    self.write(f"{label}: {self.result_path}; {summary['total_measurements']} genuine API rows. Summary saved beside CSV.", "READBACK")
                    for series, count in summary["counts"].items():
                        self.write(f"{series}: {count} stored measurements{' (EMPTY)' if count == 0 else ''}.", "READBACK")
                    self.write(f"Export finished UTC: {support.utc_now()}. No measurements sent; files were not opened automatically.", "READBACK")
                elif event[0] == "message":
                    self.write(event[2], event[1])
        except queue.Empty:
            pass
        if self.closing and not (self.worker and self.worker.is_alive()):
            self.root.destroy()
            return
        self.root.after(100, self.poll)


def main():
    root = tk.Tk()
    try:
        ControlPanel(root)
    except (ValueError, OSError):
        messagebox.showerror("Cannot load dataset", "Check data/demo_hvac.csv.")
        root.destroy()
        return
    root.mainloop()


if __name__ == "__main__":
    main()

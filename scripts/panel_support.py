"""Local helpers for the optional panel: evidence, target checks, and opening files.

No standalone command or network calls live here. Authentication, mapping checks,
history paging, and CSV/summary writing remain in the existing reader modules.
"""

from datetime import datetime, timezone
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import unquote, urlsplit

from read_readings import utc_bound, utc_text
from tandem_api import full_key


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def filename_time():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def sanitize(message):
    """Defense in depth; callers must also avoid raw exception/configuration text."""
    text = str(message).replace("\r", " ").replace("\n", " ")
    text = re.sub(r"https?://\S+", "[URL hidden]", text, flags=re.I)
    text = re.sub(
        r"\b(APS_CLIENT_ID|APS_CLIENT_SECRET|client_secret|access_token|token|authorization)"
        r"\s*[:=]\s*(?:Bearer\s+)?(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)",
        r"\1=[hidden]", text, flags=re.I)
    return text


class SessionLog:
    """UTC GUI messages only, with explicit PREVIEW / SEND / READBACK categories."""

    def __init__(self):
        self.lines = []

    def append(self, category, message):
        if category not in {"INFO", "PREVIEW", "SEND", "READBACK", "FILE"}:
            raise ValueError("Unknown session message category.")
        line = f"{utc_now()} [{category}] {sanitize(message)}"
        self.lines.append(line)
        return line

    def text(self):
        return ("GUI session log (not captured terminal stdout)\n"
                "HTTP acceptance does not establish historical storage.\n"
                + "\n".join(self.lines) + "\n")


def save_session_log(path, text, replace=False):
    """Create exclusively, or replace atomically only after explicit confirmation."""
    path = Path(path)
    if path.is_symlink():
        raise ValueError("Choose a regular session-log file.")
    if not replace:
        created = False
        try:
            with path.open("x", encoding="utf-8", newline="\n") as target:
                created = True
                target.write(text)
        except BaseException:
            if created:
                path.unlink(missing_ok=True)
            raise
        return
    # A failed replacement must not truncate the previously saved evidence.
    pending = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=path.parent, delete=False) as target:
            pending = Path(target.name)
            target.write(text)
        pending.replace(path)
    finally:
        if pending is not None:
            pending.unlink(missing_ok=True)


def suggested_bounds(run, padding_seconds=60):
    """Expand a completed run's client bounds without modifying the original record."""
    if (not isinstance(padding_seconds, int) or isinstance(padding_seconds, bool)
            or padding_seconds < 0):
        raise ValueError("Padding must be nonnegative whole seconds.")
    start, end = utc_bound(run["from_utc"]), utc_bound(run["to_utc"])
    if start > end:
        raise ValueError("Run bounds are reversed.")
    return utc_text(start - padding_seconds * 1000), utc_text(end + padding_seconds * 1000)


def verify_correspondence(config, targets):
    """Compare both URL model/stream IDs with private readback IDs, never names.

    targets contains already validated, credential-free endpoints from the sender.
    Short/full connection keys normalize using the reader's existing helper.
    """
    facility = config.get("facility_urn")
    if not isinstance(facility, str) or not facility.startswith("urn:adsk.dtt:"):
        raise ValueError("Fill facility_urn in config/readback.json. See docs/READBACK.md.")
    if set(targets) != set(config["connections"]):
        raise ValueError("Configure every equipment connection. See docs/READBACK.md.")
    model = facility.replace("urn:adsk.dtt:", "urn:adsk.dtm:", 1)
    for equipment, (endpoint, _) in targets.items():
        parts = urlsplit(endpoint).path.strip("/").split("/")
        if (len(parts) != 7 or parts[:4] != ["api", "v1", "timeseries", "models"]
                or parts[5] != "streams"):
            raise ValueError("Cannot identify ingestion destinations. See docs/READBACK.md.")
        if (unquote(parts[4]) != model or full_key(unquote(parts[6]))
                != full_key(config["connections"][equipment]["connection_key"])):
            raise ValueError("Panel URLs and readback IDs differ. Check private configuration and discovery in docs/READBACK.md.")


def open_result(path, folder=False):
    """Explicit user action only; use the OS association, without a shell or Excel."""
    path = Path(path).resolve()
    if not path.is_file():
        raise OSError("Export no longer exists.")
    target = path.parent if folder else path
    if sys.platform == "win32":
        os.startfile(str(target))
    else:
        try:
            subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", str(target)],
                           check=True, capture_output=True, timeout=5)
        except (OSError, subprocess.SubprocessError):
            raise OSError("The OS could not confirm opening the saved result.") from None

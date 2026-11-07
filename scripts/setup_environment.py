"""Create/check this project's environment, preserving unusable copies for recovery."""

from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]


def environment_python(folder):
    return folder / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def usable(folder):
    """Probe the environment's own interpreter; copied environments may not start."""
    python = environment_python(folder)
    if not python.is_file():
        return False
    try:
        result = subprocess.run([str(python), "-I", "-c",
                                 "import sys,venv; raise SystemExit(sys.version_info < (3,11))"],
                                capture_output=True, timeout=30)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def setup(root=ROOT):
    """Install pinned packages locally; no Tandem configuration or credentials needed."""
    if sys.version_info < (3, 11):
        raise RuntimeError("Install Python 3.11 or later.")
    root = root.resolve()
    folder = root / ".venv"
    if folder.is_symlink():
        raise RuntimeError("Use a local .venv directory, not a symbolic link.")
    if folder.resolve().parent != root:
        raise RuntimeError("Environment must resolve inside the project root.")
    if folder.exists() and not usable(folder):
        backup = root / (".venv.unusable-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
        folder.rename(backup)
        print(f"Preserved unusable environment as {backup.name}", flush=True)
    if not folder.exists():
        venv.EnvBuilder(with_pip=True).create(folder)
    python = str(environment_python(folder))
    subprocess.run([python, "-m", "pip", "install", "-r", str(root / "requirements-lock.txt")], check=True)
    subprocess.run([python, "-m", "pip", "check"], check=True)
    subprocess.run([python, "-B", "-c", "import requests; print('requests', requests.__version__)"], check=True)
    print("Environment ready. Start with the README preview command.")


if __name__ == "__main__":
    try:
        setup()
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"Setup failed: {error}", file=sys.stderr)
        sys.exit(1)

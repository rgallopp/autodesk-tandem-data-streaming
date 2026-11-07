"""Build an optional review ZIP from explicitly selected current source files.

The working folder remains authoritative. Never recursively archive it: private
configuration and generated outputs can coexist with publishable sources.
"""

from pathlib import Path
import hashlib
import re
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_PATHS = (
    "README.md", "LICENSE", ".gitignore", ".gitattributes", ".env.example", "requirements.txt", "requirements-lock.txt",
    "Setup-Environment.cmd", "Open-Tandem-Controls.cmd", "logs/.gitkeep", "outputs/.gitkeep",
    "data/demo_hvac.csv", "data/README.md", "config/config.example.json", "config/readback.example.json",
    "scripts/README.md", "scripts/panel_support.py",
    "scripts/build_distribution.py", "scripts/generate_demo_data.py", "scripts/measurements.py",
    "scripts/ingest-data-individual-stream-from-csv.py", "scripts/tandem-control-panel.py",
    "scripts/setup_environment.py", "scripts/read_readings.py", "scripts/tandem_api.py",
    "tests/test_sender.py", "tests/test_readback.py", "tests/test_setup_and_distribution.py",
    "tests/test_demo_data.py", "tests/test_panel.py",
    "docs/ADAPTING.md", "docs/LIVE_VERIFICATION.md", "docs/READBACK.md", "docs/REFERENCES.md",
    "docs/TANDEM_SETUP.md", "docs/TROUBLESHOOTING.md", "docs/VERIFICATION.md",
)


def public_files(root=ROOT):
    return [root / name for name in PUBLIC_PATHS]


def build(root=ROOT):
    root = root.resolve()
    contents = {}
    for path in public_files(root):
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("Public source must be a regular file inside the project.")
        data = path.read_bytes()
        if re.search(rb'https?://[^\s\x00\"\'<>]*:[^\s\x00\"\'<>]+@', data):
            raise ValueError("Credential-bearing URL candidate found; review source privately.")
        contents[path.relative_to(root).as_posix()] = data
    manifest = ''.join(f"{hashlib.sha256(data).hexdigest()}  {name}\n"
                       for name, data in sorted(contents.items())).encode("utf-8")
    contents["MANIFEST.sha256"] = manifest
    output = root / "dist/autodesk-tandem-data-streaming.zip"
    output.parent.mkdir(exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output.parent, suffix=".zip", delete=False) as temporary:
        pending = Path(temporary.name)
    try:
        with zipfile.ZipFile(pending, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in sorted(contents.items()):
                info = zipfile.ZipInfo("autodesk-tandem-data-streaming/" + name)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, data)
        pending.replace(output)
    finally:
        pending.unlink(missing_ok=True)
    print(f"Built {output}")
    print(f"Review archive: {len(contents) - 1} source files plus SHA-256 manifest. Live verification remains pending.")
    return output


if __name__ == "__main__":
    build()

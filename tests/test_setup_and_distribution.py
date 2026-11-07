"""Check setup/packaging in temporary folders without installing or launching the GUI."""

from pathlib import Path
import hashlib
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import setup_environment as setup
import build_distribution as distribution


class SetupTests(unittest.TestCase):
    def test_unusable_environment_preserved_and_rebuilt(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / ".venv").mkdir()
            (root / ".venv/marker").write_text("preserve")
            with mock.patch.object(setup, "usable", return_value=False), \
                 mock.patch.object(setup.venv, "EnvBuilder") as builder, \
                 mock.patch.object(setup.subprocess, "run") as run:
                setup.setup(root)
            backups = list(root.glob(".venv.unusable-*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual((backups[0] / "marker").read_text(), "preserve")
            builder.return_value.create.assert_called_once_with(root / ".venv")
            self.assertEqual(run.call_count, 3)

    def test_distribution_allowlist_excludes_private_working_files(self):
        paths = {p.relative_to(ROOT).as_posix() for p in distribution.public_files()}
        self.assertNotIn("config/config.json", paths)
        self.assertNotIn("config/readback.json", paths)
        self.assertNotIn(".env", paths)
        self.assertIn(".env.example", paths)
        self.assertNotIn("logs/hvac_send_log.csv", paths)
        self.assertTrue(all(not p.startswith((".venv/", ".verification/", "student-release/")) for p in paths))
        self.assertIn("scripts/read_readings.py", paths)
        self.assertIn("config/readback.example.json", paths)
        self.assertIn("data/demo_hvac.csv", paths)
        self.assertNotIn("data/payloads_dataset.csv", paths)

    @unittest.skipUnless(sys.platform == "win32", "Windows launcher check")
    def test_actual_windows_launcher_preflight(self):
        lines = (ROOT / "Open-Tandem-Controls.cmd").read_text().splitlines()
        preflight = next(line for line in lines if "sys.version_info" in line)
        # Do not launch the GUI or install packages. Exercise the shipped cmd quoting.
        with tempfile.TemporaryDirectory() as folder:
            command = Path(folder) / "check.cmd"
            command.write_text('@echo off\ncd /d "' + str(ROOT) + '"\n' + preflight + '\n')
            result = subprocess.run(["cmd.exe", "/d", "/c", str(command)], capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, "Launcher preflight failed; check cmd quoting and Tkinter")

    def test_built_archive_bytes_manifest_and_exclusions(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for source in distribution.public_files():
                target = root / source.relative_to(ROOT)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
            (root / "config/config.json").write_text('"private-bait"')
            (root / "config/readback.json").write_text("synthetic-private-readback-bait")
            (root / ".env").write_text("APS_CLIENT_SECRET=synthetic-private-bait\n")
            (root / "data/payloads_dataset.csv").write_text("excluded-original")
            (root / "scripts/unlisted.py").write_text("unlisted-bait")
            path = distribution.build(root)
            with zipfile.ZipFile(path) as archive:
                self.assertIsNone(archive.testzip())
                prefix = "autodesk-tandem-data-streaming/"
                names = {name.removeprefix(prefix) for name in archive.namelist()}
                self.assertEqual(names, set(distribution.PUBLIC_PATHS) | {"MANIFEST.sha256"})
                for entry in archive.read(prefix + "MANIFEST.sha256").decode().splitlines():
                    expected, name = entry.split("  ", 1)
                    self.assertEqual(hashlib.sha256(archive.read(prefix + name)).hexdigest(), expected)
                    self.assertEqual(archive.read(prefix + name), (ROOT / name).read_bytes())

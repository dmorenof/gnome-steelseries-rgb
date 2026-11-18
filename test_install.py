"""Installation rollback, desktop quoting and source-archive boundary tests."""

import hashlib
import json
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import build_source
from desktop_integration import desktop_entry
from distribution import DOCUMENTATION_FILES, RUNTIME_FILES, SOURCE_FILES
from install import install


class InstallationTests(unittest.TestCase):
    def source_fixture(self, directory):
        source = Path(directory) / "source"
        for name in RUNTIME_FILES + DOCUMENTATION_FILES:
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixture\n")
        return source

    def test_staged_install_preserves_settings_and_disabled_restoration(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home with spaces % $"
            source = self.source_fixture(directory)
            settings = home / ".config/titan-rgb/settings.json"
            settings.parent.mkdir(parents=True)
            settings.write_text(
                json.dumps({"color": "#ff0000", "brightness": 40, "autostart": False})
            )
            original = settings.read_bytes()
            with patch("install.subprocess.run"):
                target = install(home, source)
                install(home, source)
            self.assertEqual(settings.read_bytes(), original)
            self.assertFalse((home / ".config/autostart/titan-rgb.desktop").exists())
            self.assertEqual((target / "app.py").read_text(), "fixture\n")
            self.assertTrue((target / "vendor/LICENSE").is_file())
            self.assertIn(
                "%%", (home / ".local/share/applications/local.steelseries.rgb.desktop").read_text()
            )
            self.assertEqual(list(target.parent.glob(".titan-rgb-stage-*")), [])

    def test_failed_swap_restores_previous_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            source = self.source_fixture(directory)
            target = home / ".local/share/titan-rgb"
            target.mkdir(parents=True)
            (target / "app.py").write_text("original")
            import os

            replace = os.replace

            def fail_once(origin, destination):
                if (
                    Path(origin).name.startswith(".titan-rgb-stage-")
                    and not str(origin).endswith("-previous")
                    and Path(destination) == target
                ):
                    raise OSError("simulated installation failure")
                return replace(origin, destination)

            with patch("install.os.replace", side_effect=fail_once):
                with self.assertRaises(OSError):
                    install(home, source)
            self.assertEqual((target / "app.py").read_text(), "original")

    def test_missing_file_does_not_modify_installed_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            source = self.source_fixture(directory)
            (source / "vendor/LICENSE").unlink()
            with self.assertRaises(FileNotFoundError):
                install(home, source)
            self.assertFalse((home / ".local").exists())

    def test_desktop_path_control_characters_are_rejected(self):
        with self.assertRaises(ValueError):
            desktop_entry(Path("/tmp/path\nInjected=true"))

    def test_desktop_launch_preserves_literal_special_characters(self):
        from gi.repository import Gio

        with tempfile.TemporaryDirectory() as directory:
            application = Path(directory) / 'space % dollar $ quote " slash \\ tick `'
            application.mkdir()
            script = application / "app.py"
            script.write_text(
                'import json,sys\nfrom pathlib import Path\nPath(__file__).with_suffix(".json").write_text(json.dumps(sys.argv))\n'
            )
            desktop = Path(directory) / "test.desktop"
            desktop.write_text(desktop_entry(application))
            launcher = Gio.DesktopAppInfo.new_from_filename(str(desktop))
            self.assertIsNotNone(launcher)
            self.assertTrue(launcher.launch([], None))
            output = script.with_suffix(".json")
            deadline = time.monotonic() + 3
            while not output.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertEqual(json.loads(output.read_text()), [str(script)])

    def test_archive_is_complete_deterministic_and_public_only(self):
        with tempfile.TemporaryDirectory() as directory:
            first = build_source.build(Path(directory) / "first.zip")
            second = build_source.build(Path(directory) / "second.zip")
            self.assertEqual(
                hashlib.sha256(first.read_bytes()).digest(),
                hashlib.sha256(second.read_bytes()).digest(),
            )
            with zipfile.ZipFile(first) as archive:
                expected = {"steelseries-rgb-gnome/" + name for name in SOURCE_FILES}
                self.assertEqual(set(archive.namelist()), expected)
                self.assertIsNone(archive.testzip())
                self.assertNotIn("work/", "".join(archive.namelist()))

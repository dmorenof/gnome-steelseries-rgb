"""Regression coverage for user-data loss and malformed input boundaries."""

import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import remote_profiles
from color_math import rgb_value
from openrgb_control import parse_snapshot
from profile_binding import validate_profile
from settings import DEFAULT, SettingsStore
from storage import StorageError, create_bytes, decode_json, write_json
from test_openrgb_control import description


class StorageTests(unittest.TestCase):
    def test_corrupt_and_future_settings_are_preserved(self):
        invalid = [
            "{broken",
            "[]",
            '{"schema_version":true}',
            '{"schema_version":999}',
            '{"brightness":NaN}',
            '{"autostart":"false"}',
            '{"profiles":{"bad":{"brightness":20}}}',
            '{"key_colors":{"4":"invalid"}}',
            '{"color":"#ffffff","color":"#000000"}',
        ]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            for content in invalid:
                path.write_text(content)
                store = SettingsStore(path)
                with self.assertRaises(StorageError):
                    store.load()
                with self.assertRaises(StorageError):
                    store.save(DEFAULT)
                self.assertEqual(path.read_text(), content)

    def test_concurrent_edits_do_not_overwrite_another_process(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            first, second = SettingsStore(path), SettingsStore(path)
            a, b = first.load(), second.load()
            a["color"] = "#ff0000"
            first.save(a)
            b["color"] = "#00ff00"
            with self.assertRaisesRegex(StorageError, "another process"):
                second.save(b)
            self.assertEqual(SettingsStore(path).load()["color"], "#ff0000")

    def test_atomic_failure_preserves_original_and_removes_temporary_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            write_json(path, {"original": True})
            with patch("storage.os.replace", side_effect=OSError("disk failure")):
                with self.assertRaises(OSError):
                    write_json(path, {"replacement": True})
            self.assertEqual(json.loads(path.read_text()), {"original": True})
            self.assertEqual(list(Path(folder).iterdir()), [path])

    def test_failed_exclusive_file_creation_is_removed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "backup.json"
            with patch("storage.os.fsync", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    create_bytes(path, b"original bytes")
            self.assertFalse(path.exists())
            create_bytes(path, b"original bytes")
            with self.assertRaises(FileExistsError):
                create_bytes(path, b"replacement")
            self.assertEqual(path.read_bytes(), b"original bytes")

    def test_oversized_settings_are_rejected_before_json_decode(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            raw = b" " * 1048577
            path.write_bytes(raw)
            with self.assertRaises(StorageError):
                SettingsStore(path).load()
            self.assertEqual(path.read_bytes(), raw)

    def test_remote_profile_updates_are_serialized(self):
        snapshot = parse_snapshot(description())
        errors = []

        def put(name):
            try:
                remote_profiles.put(snapshot, name, ["#ffffff"] * 3, 40)
            except Exception as error:
                errors.append(error)

        with (
            tempfile.TemporaryDirectory() as folder,
            patch("remote_profiles.path", return_value=Path(folder) / "profiles.json"),
        ):
            threads = [threading.Thread(target=put, args=(name,)) for name in ("one", "two")]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(3)
                self.assertFalse(thread.is_alive())
            self.assertEqual(errors, [])
            self.assertEqual(set(remote_profiles.names(snapshot)), {"one", "two"})

    def test_invalid_numbers_and_duplicate_keys(self):
        for value in (True, None, "50", float("nan"), float("inf"), -1, 101):
            with self.assertRaises(ValueError):
                rgb_value("#ffffff", value)
        for raw in ('{"a":1,"a":2}', '{"a":NaN}', "[[[[", b"\xff"):
            with self.assertRaises(StorageError):
                decode_json(raw)
        for overrides in ([], {"4": "bad"}, {"04": "#ff0000"}, {"0": "#ffffff"}):
            with self.assertRaises(ValueError):
                validate_profile({**DEFAULT, "key_colors": overrides})

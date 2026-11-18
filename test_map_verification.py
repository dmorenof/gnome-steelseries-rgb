import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from keyboard_layout import KEYS
from map_verification import MAP_REVISION, Verification, key_name


class MappingTests(unittest.TestCase):
    def test_requires_explicit_valid_observation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "verification.json"
            store = Verification(path)
            self.assertEqual(store.states(), {})
            self.assertFalse(path.exists())
            for code, result in [(999, "correct"), (4, "usb-transmitted")]:
                with self.assertRaises(ValueError):
                    store.record(code, result)
            self.assertFalse(path.exists())
            store.record(4, "correct")
            store.record(5, "different", "Otra tecla")
            report = store.report()
            self.assertEqual(report["total_keys"], 102)
            self.assertEqual(report["keys"]["4"]["source"], "user-observation")
            self.assertEqual(report["keys"]["5"]["note"], "Otra tecla")
            self.assertNotIn("color", report)
            self.assertNotIn("profiles", report)

    def test_map_revision_does_not_reuse_old_confirmations(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Verification(Path(tmp) / "verification.json")
            store.record(4, "correct")
            with patch("map_verification.MAP_REVISION", "new-map"):
                self.assertEqual(store.states(), {})
                store.record(5, "no-change")
                self.assertEqual(set(store.states()), {"5"})
            self.assertEqual(set(store.states()), {"4"})

    def test_corrupt_file_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "verification.json"
            path.write_text("broken")
            store = Verification(path)
            with self.assertRaises(RuntimeError):
                store.record(4, "correct")
            self.assertEqual(path.read_text(), "broken")

    def test_unknown_or_automatic_results_not_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "verification.json"
            store = Verification(path)
            store.record(4, "correct")
            data = json.loads(path.read_text())
            entries = data["maps"][MAP_REVISION]["keys"]
            entries["4"]["source"] = "usb"
            entries["999"] = {"result": "correct", "source": "user-observation"}
            path.write_text(json.dumps(data))
            self.assertEqual(store.states(), {})

    def test_labels_distinguish_duplicate_keys(self):
        names = [key_name(key) for key in KEYS]
        self.assertIn("Ctrl izquierdo", names)
        self.assertIn("Ctrl derecho", names)
        self.assertIn("Intro · numérico", names)
        self.assertIn("Intro", names)


if __name__ == "__main__":
    unittest.main()

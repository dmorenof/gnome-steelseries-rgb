import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app
from backend import Keyboard, rgb_value
from effects import KEYS, TEMPLATES, frame
from vendor.keycodes import REGION_KEYCODES
from vendor.msiprotocol import make_key_colors_packet


class Checks(unittest.TestCase):
    def test_version_and_help_work_without_site_packages(self):
        for flag in ("--version", "--help"):
            result = subprocess.run(
                [sys.executable, "-S", str(Path(app.__file__)), flag],
                capture_output=True,
                text=True,
                timeout=5,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run(
            [sys.executable, "-S", str(Path(app.__file__)), "--invalid-option"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(result.returncode, 2)

    def test_legacy_worker_matching_is_restricted(self):
        from engine import worker_command

        origins = {b"/known/engine.py"}
        self.assertTrue(
            worker_command([b"python3", b"/known/engine.py", b"--worker", b"Aqua"], origins)
        )
        self.assertFalse(worker_command([b"python3", b"/other/engine.py", b"--worker"], origins))
        self.assertFalse(worker_command([b"python3", b"/known/engine.py", b"--smoke"], origins))
        self.assertFalse(worker_command([b"python3"], origins))

    def test_key_hit_testing_at_multiple_sizes(self):
        from keyboard_layout import HEIGHT, WIDTH, hit_test
        from keyboard_layout import KEYS as diagram

        for width, height in [(600, 295), (1050, 340), (1400, 500)]:
            unit = min((width - 12) / WIDTH, (height - 12) / HEIGHT)
            ox = (width - WIDTH * unit) / 2
            oy = (height - HEIGHT * unit) / 2
            for key in diagram:
                self.assertIs(
                    hit_test(
                        ox + (key["x"] + key["w"] / 2) * unit,
                        oy + (key["y"] + key["h"] / 2) * unit,
                        width,
                        height,
                    ),
                    key,
                )
            self.assertIsNone(hit_test(0, 0, width, height))
            enter = next(k for k in diagram if k["shape"] == "iso-enter")
            self.assertEqual(
                hit_test(
                    ox + (enter["x"] + 0.1) * unit, oy + (enter["y"] + 1.5) * unit, width, height
                )["label"],
                "Ç",
            )
        self.assertEqual(len({k["code"] for k in diagram}), 102)

    def test_individual_color_preserves_other_keys(self):
        from keyboard_layout import KEYS as diagram
        from keyboard_layout import preview_colors
        from lighting import clean_key_colors, compose

        for effect in ["solid"] + list(TEMPLATES):
            before = compose("#64a8ff", 60, effect)
            after = compose("#64a8ff", 60, effect, {"4": "#ff0000", "93": "#00ff00"})
            self.assertEqual(after[4], (153, 0, 0))
            self.assertEqual(after[93], (0, 153, 0))
            self.assertEqual(
                {k: v for k, v in before.items() if k not in (4, 93)},
                {k: v for k, v in after.items() if k not in (4, 93)},
            )
            self.assertEqual(
                preview_colors("#64a8ff", 60, effect, {"4": "#ff0000"}),
                [compose("#64a8ff", 60, effect, {"4": "#ff0000"})[k["code"]] for k in diagram],
            )
            self.assertTrue(
                all(
                    rgb == (0, 0, 0)
                    for rgb in compose("#64a8ff", 0, effect, {"4": "#ff0000"}).values()
                )
            )
        self.assertEqual(
            clean_key_colors(
                {"4": "#ffffff", "0": "#ff0000", "999": "#ff0000", "93": "bad", "wrong": None}
            ),
            {"4": "#ffffff"},
        )

    def test_individual_colors_survive_profile_storage(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(app, "CONFIG", Path(directory) / "settings.json"),
        ):
            data = app.load()
            data["key_colors"] = {"4": "#ff0000"}
            data["profiles"]["Individual"] = {
                "color": "#64a8ff",
                "brightness": 60,
                "effect": "Aqua",
                "key_colors": {"93": "#00ff00"},
            }
            app.save(data)
            loaded = app.load()
            self.assertEqual(loaded["key_colors"], {"4": "#ff0000"})
            self.assertEqual(loaded["profiles"]["Individual"]["key_colors"], {"93": "#00ff00"})

    def test_session_layout_detection(self):
        from gi.repository import Gio

        from layout_detection import detect_layout

        class Settings:
            def __init__(self, sources):
                self.sources = sources

            def get_value(self, key):
                from gi.repository import GLib

                return GLib.Variant("a(ss)", self.sources)

        for sources, expected in [
            ([("xkb", "es")], "gt76-es-iso"),
            ([("xkb", "us")], None),
            ([("xkb", "es"), ("xkb", "us")], None),
            ([], None),
        ]:
            with patch.object(Gio.Settings, "new", return_value=Settings(sources)):
                self.assertEqual(detect_layout()["diagram"], expected)

    def test_preview_matches_static_frame(self):
        from keyboard_layout import KEYS as diagram
        from keyboard_layout import preview_colors

        self.assertEqual(len(diagram), 102)
        self.assertTrue(all(key["code"] is not None for key in diagram))
        self.assertEqual(preview_colors("#ff8000", 50), [(128, 64, 0)] * 102)
        for name in TEMPLATES:
            colors = frame(name, 0, 60)
            self.assertEqual(
                preview_colors("#ffffff", 60, name),
                [colors.get(key["code"], (0, 0, 0)) for key in diagram],
            )
            self.assertEqual(preview_colors("#ffffff", 0, name), [(0, 0, 0)] * 102)
        self.assertEqual(next(k["code"] for k in diagram if k["label"] == "5" and k["x"] < 16), 34)
        self.assertEqual(next(k["code"] for k in diagram if k["label"] == "5" and k["x"] > 16), 93)

    def test_uniform_payload_is_complete_and_repeatable(self):
        from backend import apply_color

        class FakeHID:
            def __init__(self):
                self.sent = []

            def hid_send_feature_report(self, dev, data, size):
                self.sent.append(bytes(data))
                return size

            def hid_write(self, dev, data, size):
                self.sent.append(bytes(data))
                return size

        keyboard = Keyboard()
        keyboard.dev = 1
        keyboard.lib = FakeHID()
        with patch("backend.Keyboard") as factory, patch("backend.time.sleep") as delay:
            factory.return_value.__enter__.return_value = keyboard
            for color in ("#ff0000", "#00ff00", "#0000ff", "#ffffff", "#ff8000", "#000000"):
                keyboard.lib.sent = []
                apply_color(color, 60)
                apply_color(color, 60)
                first, second = keyboard.lib.sent[:5], keyboard.lib.sent[5:]
                self.assertEqual(first, second)
                expected = rgb_value(color, 60)
                seen = []
                for packet, keys in zip(first[:4], REGION_KEYCODES.values()):
                    fragments = [packet[i : i + 12] for i in range(4, 508, 12)]
                    entries = [part for part in fragments if part[-1]]
                    self.assertEqual([part[-1] for part in entries], [k for k in keys if k])
                    for part in entries:
                        self.assertEqual(list(part[:3]), expected)
                        self.assertEqual(part[9], 1)  # static mode
                        seen.append(part[-1])
                self.assertEqual(
                    set(seen), {k for keys in REGION_KEYCODES.values() for k in keys if k}
                )
                self.assertEqual(first[4], bytes([9] + [0] * 63))
            self.assertEqual(delay.call_count, 60)  # includes wait after refresh

    def test_usb_transactions_do_not_overlap(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict("os.environ", {"XDG_RUNTIME_DIR": directory}),
        ):
            with patch.object(
                Keyboard, "_open", autospec=True, side_effect=lambda keyboard: keyboard
            ):
                first = Keyboard()
                second = Keyboard()
                first.__enter__()
                try:
                    with self.assertRaisesRegex(RuntimeError, "Otro envío"):
                        second.__enter__()
                finally:
                    first.lock.close()
                second.__enter__()
                second.lock.close()

    def test_partial_usb_error_stops_before_refresh(self):
        class FakeHID:
            def __init__(self):
                self.calls = 0

            def hid_send_feature_report(self, *args):
                self.calls += 1
                return 524 if self.calls == 1 else -1

            def hid_error(self, *args):
                return "test error"

            def hid_write(self, *args):
                raise AssertionError("No actualizar tras un fallo")

        keyboard = Keyboard()
        keyboard.dev = 1
        keyboard.lib = FakeHID()
        with patch("backend.time.sleep"), self.assertRaisesRegex(RuntimeError, "enter.*parcial"):
            keyboard.frame(frame("Plain", 0, 100))

    def test_invalid_color_and_brightness(self):
        for color, level in [
            ("#ff0000", -1),
            ("#ff0000", 101),
            ("oops", 50),
            ("#ffffff", float("nan")),
        ]:
            with self.assertRaises(ValueError):
                rgb_value(color, level)
        self.assertEqual(rgb_value("#ff8000", 50), [128, 64, 0])

    def test_protocol_bounds(self):
        for region, keys in REGION_KEYCODES.items():
            packet = make_key_colors_packet(region, {k: [30, 50, 80] for k in keys})
            self.assertEqual(len(packet), 524)
            self.assertTrue(all(0 <= v <= 255 for v in packet))

    def test_effects_only_emit_static_packets(self):
        class FakeHID:
            def __init__(self):
                self.sent = []

            def hid_send_feature_report(self, dev, data, size):
                self.sent.append(data[0])
                return size

            def hid_write(self, dev, data, size):
                self.sent.append(data[0])
                return size

        keyboard = Keyboard()
        keyboard.dev = 1
        keyboard.lib = FakeHID()
        with patch("backend.time.sleep"):
            for name in TEMPLATES:
                for t in (0, 1.1, 8.5, 100):
                    for brightness in (0, 60, 100):
                        colors = frame(name, t, brightness)
                        self.assertEqual(set(colors), KEYS)
                        keyboard.frame(colors)
                        self.assertEqual(keyboard.lib.sent[-5:], [14, 14, 14, 14, 9])
        self.assertNotIn(11, keyboard.lib.sent)

    def test_invalid_frame_sends_nothing(self):
        keyboard = Keyboard()
        keyboard.dev = 1

        class FakeHID:
            def hid_send_feature_report(self, *args):
                raise AssertionError("No debe enviarse nada")

        keyboard.lib = FakeHID()
        colors = frame("Plain", 0, 100)
        colors[99] = (0, 0, 256)
        with self.assertRaises(ValueError):
            keyboard.frame(colors)

    def test_settings_roundtrip_and_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            original = app.CONFIG
            app.CONFIG = Path(directory) / "settings.json"
            try:
                data = app.load()
                data["profiles"]["Noche"] = {"color": "#ff0000", "brightness": 20}
                app.save(data)
                self.assertEqual(app.load()["profiles"]["Noche"]["brightness"], 20)
                app.CONFIG.write_text("{broken")
                with self.assertRaises(RuntimeError):
                    app.load()
                app.CONFIG.write_text('{"color":"#ffffff","brightness":40,"profiles":[]}')

                with self.assertRaises(RuntimeError):
                    app.load()
            finally:
                app.CONFIG = original


if __name__ == "__main__":
    unittest.main()

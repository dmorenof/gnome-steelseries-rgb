import unittest
from unittest.mock import patch

from backend import Keyboard
from editor_state import EditorState
from key_selection import ALL, ORDER, KeySelection

SETTINGS = {"color": "#64a8ff", "brightness": 60, "effect": "Aqua", "key_colors": {"4": "#ff0000"}}


class SelectionTests(unittest.TestCase):
    def test_click_ctrl_shift_and_ctrl_shift(self):
        selection = KeySelection()
        a, b, c, d = ORDER[:4]
        self.assertEqual(selection.click(a), {a})
        self.assertEqual(selection.click(c, ctrl=True), {a, c})
        self.assertEqual(selection.click(a, ctrl=True), {c})
        self.assertEqual(selection.click(d, shift=True), {a, b, c, d})
        selection.click(d)
        selection.click(a, ctrl=True)
        self.assertEqual(selection.click(b, ctrl=True, shift=True), {a, b, d})
        selection.clear()
        self.assertEqual(selection.codes, set())
        self.assertIsNone(selection.anchor)
        selection.all()
        self.assertEqual(selection.codes, ALL)

    def test_unknown_state_is_not_inferred_from_cached_settings(self):
        state = EditorState(SETTINGS)
        self.assertFalse(state.full_known)
        self.assertEqual(state.known, set())
        self.assertEqual(state.brightness, 100)
        with self.assertRaises(ValueError):
            state.set_brightness(50)
        state.set_color({4, 5}, "#00ff00")
        self.assertFalse(state.full_known)
        self.assertEqual(state.known, {4, 5})
        self.assertEqual(state.partial_colors({4, 5}), {4: (0, 255, 0), 5: (0, 255, 0)})

    def test_intensity_preserves_per_key_colors_and_effect(self):
        state = EditorState(SETTINGS)
        state.load(SETTINGS)
        before = state.snapshot()
        state.set_brightness(30)
        after = state.snapshot()
        self.assertEqual(after["effect"], before["effect"])
        self.assertEqual(after["key_colors"], before["key_colors"])
        self.assertEqual(state.colors()[4], (76, 0, 0))
        state.set_color({5}, "#00ff00")
        self.assertEqual(state.colors()[5], (0, 76, 0))
        self.assertEqual(state.effect, "Aqua")

    def test_explicit_all_color_creates_complete_configuration(self):
        state = EditorState(SETTINGS)
        state.set_color(ALL, "#ffffff")
        self.assertTrue(state.full_known)
        self.assertEqual(state.effect, "solid")
        self.assertEqual(state.key_colors, {})
        state.set_brightness(50)
        self.assertEqual(set(state.colors().values()), {(128, 128, 128)})

    def test_individual_edits_can_complete_state_without_writing_unknown_keys(self):
        state = EditorState(SETTINGS)
        remaining = set(ALL) - {4}
        self.assertFalse(state.set_color(remaining, "#00ff00"))
        self.assertFalse(state.full_known)
        self.assertFalse(state.set_color({4}, "#ff0000"))
        self.assertTrue(state.full_known)
        state.set_brightness(50)
        self.assertEqual(state.colors()[4], (128, 0, 0))
        self.assertEqual({state.colors()[code] for code in remaining}, {(0, 128, 0)})


class SparsePacketTests(unittest.TestCase):
    def test_only_selected_addresses_are_transmitted(self):
        class HID:
            def __init__(self):
                self.reports = []
                self.updates = []

            def hid_send_feature_report(self, dev, data, size):
                self.reports.append(bytes(data))
                return size

            def hid_write(self, dev, data, size):
                self.updates.append(bytes(data))
                return size

        keyboard = Keyboard()
        keyboard.dev = 1
        keyboard.lib = HID()
        with patch("backend.time.sleep"):
            keyboard.set_keys({4: (255, 0, 0), 93: (0, 255, 0)})
        addresses = []
        for report in keyboard.lib.reports:
            self.assertEqual((report[0], len(report)), (14, 524))
            for offset in range(4, 508, 12):
                part = report[offset : offset + 12]
                if part[-1]:
                    addresses.append(part[-1])
        self.assertEqual(addresses, [4, 93])
        self.assertEqual(len(keyboard.lib.reports), 2)
        self.assertEqual(keyboard.lib.updates, [bytes([9] + [0] * 63)])

    def test_navigation_addresses_in_sparse_and_full_frames(self):
        from vendor.keycodes import REGION_KEYCODES

        class HID:
            def __init__(self):
                self.reports = []

            def hid_send_feature_report(self, dev, data, size):
                self.reports.append(bytes(data))
                return size

            def hid_write(self, dev, data, size):
                return size

        keyboard = Keyboard()
        keyboard.dev = 1
        keyboard.lib = HID()

        def entries():
            return {
                packet[offset + 11]: tuple(packet[offset : offset + 3])
                for packet in keyboard.lib.reports
                for offset in range(4, 508, 12)
                if packet[offset + 11]
            }

        with patch("backend.time.sleep"):
            keyboard.set_keys({74: (1, 2, 3), 77: (4, 5, 6)})
            self.assertEqual(entries(), {75: (1, 2, 3), 78: (4, 5, 6)})
            keyboard.lib.reports = []
            colors = {
                code: (255, 255, 255) for keys in REGION_KEYCODES.values() for code in keys if code
            }
            colors.update({74: (1, 2, 3), 77: (4, 5, 6)})
            keyboard.frame(colors)
            self.assertEqual(entries()[75], (1, 2, 3))
            self.assertEqual(entries()[78], (4, 5, 6))
            self.assertEqual(entries()[76], (255, 255, 255))

    def test_duplicate_physical_addresses_and_noninteger_codes_send_nothing(self):
        keyboard = Keyboard()
        keyboard.dev = 1
        keyboard.lib = unittest.mock.Mock()
        for colors in ({74: (1, 2, 3), 75: (4, 5, 6)}, {4.0: (1, 2, 3)}, {4: None}):
            with self.assertRaises(ValueError):
                keyboard.set_keys(colors)
        keyboard.lib.hid_send_feature_report.assert_not_called()

    def test_invalid_sparse_frame_sends_nothing(self):
        class HID:
            def hid_send_feature_report(self, *_):
                raise AssertionError("unexpected USB")

        keyboard = Keyboard()
        keyboard.dev = 1
        keyboard.lib = HID()
        for colors in ({}, {0: (0, 0, 0)}, {4: (0, 0, 0), 93: (0, 0, 256)}):
            with self.assertRaises(ValueError):
                keyboard.set_keys(colors)


if __name__ == "__main__":
    unittest.main()

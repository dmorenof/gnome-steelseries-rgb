import unittest

from keyboard_layout import KEYS, preview_colors


class PreviewTests(unittest.TestCase):
    def test_moving_sample_is_screen_only_and_respects_overrides(self):
        from unittest.mock import patch

        with patch("lighting.apply_lighting") as send:
            fixed = preview_colors("#ffffff", 60, "Aqua", {"4": "#ff0000"}, 0)
            moving = preview_colors("#ffffff", 60, "Aqua", {"4": "#ff0000"}, 8)
            self.assertNotEqual(fixed, moving)
            index = next(i for i, key in enumerate(KEYS) if key["code"] == 4)
            self.assertEqual(fixed[index], moving[index])
            self.assertEqual(moving[index], (153, 0, 0))
            send.assert_not_called()

    def test_no_intensity_or_solid_stays_static(self):
        for effect in ("solid", "Plain"):
            self.assertEqual(
                preview_colors("#336699", 100, effect, {}, 0),
                preview_colors("#336699", 100, effect, {}, 8),
            )
        self.assertEqual(set(preview_colors("#ffffff", 0, "Aqua", {}, 8)), {(0, 0, 0)})


if __name__ == "__main__":
    unittest.main()

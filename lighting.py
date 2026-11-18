"""Compose a single static frame shared by preview, profiles and USB output."""

from backend import Keyboard
from color_math import rgb_value
from effects import KEYS, TEMPLATES, frame


def clean_key_colors(value):
    result = {}
    if not isinstance(value, dict):
        return result
    for key, color in value.items():
        try:
            code = int(key)
            if str(code) != str(key) or code == 0 or code not in KEYS:
                continue
            rgb_value(color, 100)
            result[str(code)] = color
        except (ValueError, TypeError):
            continue
    return result


def compose(color, brightness, effect="solid", key_colors=None):
    colors = (
        frame(effect, 0, brightness)
        if effect in TEMPLATES
        else {k: tuple(rgb_value(color, brightness)) for k in KEYS}
    )
    for code, value in clean_key_colors(key_colors).items():
        colors[int(code)] = tuple(rgb_value(value, brightness))
    return colors


def apply_lighting(color, brightness, effect="solid", key_colors=None):
    colors = compose(color, brightness, effect, key_colors)
    with Keyboard() as keyboard:
        keyboard.frame(colors)

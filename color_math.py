"""Validated RGB scaling shared by editors and device adapters."""

import re


def rgb_value(color, brightness):
    if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        raise ValueError("El color debe tener el formato #RRGGBB.")
    if type(brightness) not in (int, float) or not 0 <= brightness <= 100:
        raise ValueError("El brillo debe estar entre 0 y 100.")
    brightness = float(brightness)
    if not 0 <= brightness <= 100:
        raise ValueError("El brillo debe estar entre 0 y 100.")
    return [round(int(color[i : i + 2], 16) * brightness / 100) for i in (1, 3, 5)]

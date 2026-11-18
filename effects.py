"""Compatible static recreations. Host streaming is disabled after physical flicker testing."""

import colorsys
import math
import random

from color_math import rgb_value
from vendor.keycodes import REGION_KEYCODES

TEMPLATES = {
    "Plain": "Amarillo fijo, como la plantilla Plain documentada por MSI.",
    "Aqua": "Muestra fija en tonos azules y turquesas.",
    "Chakra": "Muestra fija de color.",
    "Disco": "Mosaico fijo de colores por tecla.",
    "Drain": "Patrón fijo de luz hacia el centro.",
    "Freeway": "Mosaico fijo de colores e intensidades.",
    "Rainbow Split": "Arcoíris fijo desde el centro hacia los lados.",
    "Roulette": "Banda fija de color.",
}
KEYS = set(k for group in REGION_KEYCODES.values() for k in group if k)
POSITIONS = {}
for y, row in enumerate(
    [
        [41, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72],
        [53, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 45, 46, 42],
        [43, 20, 26, 8, 21, 23, 28, 24, 12, 18, 19, 47, 48, 49],
        [57, 4, 22, 7, 9, 10, 11, 13, 14, 15, 51, 52, 40],
        [225, 100, 29, 27, 6, 25, 5, 17, 16, 54, 55, 56, 229],
        [224, 227, 226, 44, 230, 240, 228, 80, 81, 79],
    ]
):
    for x, key in enumerate(row):
        POSITIONS[key] = (x, y)
for key in range(83, 100):
    POSITIONS[key] = (16 + (key - 83) % 4, (key - 83) // 4 + 1)
POSITIONS[82] = (11, 4)


def hsv(h, s, v):
    return tuple(round(c * 255) for c in colorsys.hsv_to_rgb(h % 1, s, max(0, min(1, v))))


def random_color(key, step):
    rng = random.Random(key * 7919 + step * 104729)
    return hsv(rng.random(), 0.8, 1)


def frame(name, t, brightness):
    if name not in TEMPLATES:
        raise ValueError("Plantilla desconocida.")
    factor = float(brightness) / 100
    rgb_value("#000000", brightness)
    colors = {}
    for key in KEYS:
        x, y = POSITIONS.get(key, (8, 3))
        if name == "Plain":
            color = (255, 255, 0)
        elif name == "Aqua":
            color = hsv(
                0.52 + 0.045 * math.sin(x * 0.22 - t * 0.25),
                0.82,
                0.72 + 0.28 * (1 + math.sin(x * 0.36 - t * 0.40)) / 2,
            )
        elif name == "Chakra":
            color = hsv(t / 32, 0.85, 1)
        elif name in ("Disco", "Freeway"):
            span = 9.0
            step = int(t / span)
            phase = (t / span) % 1
            f = phase * phase * (3 - 2 * phase)
            a = random_color(key, step)
            b = random_color(key, step + 1)
            pulse = 1 if name == "Disco" else 0.25 + 0.75 * (1 + math.sin(t * 0.35 + key)) / 2
            color = tuple(round((a[i] * (1 - f) + b[i] * f) * pulse) for i in range(3))
        elif name == "Rainbow Split":
            color = hsv(abs(x - 8) / 24 - t / 24, 0.9, 1)
        elif name == "Roulette":
            distance = min(abs((x / 20 - t / 24) % 1), abs((t / 24 - x / 20) % 1))
            color = hsv(t / 24, 0.85, 0.12 + 0.88 * math.exp(-distance * distance * 100))
        else:
            color = hsv(0.58, 0.75, 0.1 + 0.9 * max(0, math.sin(abs(x - 8) * 0.55 + t * 0.35)) ** 3)
        colors[key] = tuple(round(c * factor) for c in color)
    return colors

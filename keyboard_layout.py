"""GT76 Titan Spanish ISO keyboard diagram, 102 keys.
Geometry based on MSI's compatible replacement and photos of GT76 DT 9SF ES.
Lighting editor uses an experimental association with inherited protocol codes.
The physical RGB address of every key still needs user validation.
"""

import math

from devices import GT76_RGB_ADDRESSES

KEYS = []


def add(label, x, y, w=1, h=1, shape=None):
    KEYS.append(dict(label=label, x=x, y=y, w=w, h=h, shape=shape))


def row(labels, y, x=0):
    for value in labels:
        label, w = value if isinstance(value, tuple) else (value, 1)
        add(label, x, y, w)
        x += w
    return x


# Compact full function row and the four navigation keys above the keypad.
for i, label in enumerate(
    ["Esc"] + [f"F{n}" for n in range(1, 13)] + ["Impr\nPant", "Bloq\nDespl", "Pausa"]
):
    add(label, i * 15.5 / 16, 0, 15.5 / 16, 0.72)
for i, label in enumerate(["Insert", "Supr", "Inicio", "Fin"]):
    add(label, 16.5 + i, 0, 1, 0.72)
row(["º ª"] + [str(i) for i in range(1, 10)] + ["0", "' ?", "¡ ¿", ("Retroceso", 2.5)], 0.95)
row([("Tab", 1.5)] + list("QWERTYUIOP") + ["` ^", "+ *"], 2)
add("Intro", 13.5, 2, 2, 2.05, "iso-enter")
row([("Bloq Mayús", 1.75)] + list("ASDFGHJKL") + ["Ñ", "´ ¨", "Ç"], 3.05)
row([("Mayús", 2.25)] + list("ZXCVBNM") + [", ;", ". :", "- _", ("Mayús", 3.25), "↑"], 4.10)
row(
    [
        ("Ctrl", 1.25),
        ("Fn", 0.75),
        ("Alt", 1.25),
        ("Espacio", 7.25),
        "< >",
        "Alt Gr",
        "Win",
        "Ctrl",
        "←",
        "↓",
        "→",
    ],
    5.15,
)
# Narrow MSI keypad: its zero is a single key, and the arrow cluster reaches
# into the bottom-left keypad position.
for label, x, y in [
    ("Bloq\nNum", 16.5, 0.95),
    ("/", 17.5, 0.95),
    ("*", 18.5, 0.95),
    ("−", 19.5, 0.95),
    ("7\nInicio", 16.5, 2),
    ("8 ↑", 17.5, 2),
    ("9\nRe Pág", 18.5, 2),
    ("4 ←", 16.5, 3.05),
    ("5", 17.5, 3.05),
    ("6 →", 18.5, 3.05),
    ("1\nFin", 16.5, 4.10),
    ("2 ↓", 17.5, 4.10),
    ("3\nAv Pág", 18.5, 4.10),
    ("0\nInsert", 17.5, 5.15),
    (".\nSupr", 18.5, 5.15),
]:
    add(label, x, y)
add("+", 19.5, 2, 1, 2.05)
add("Intro", 19.5, 4.10, 1, 2.05)
WIDTH = 20.5
HEIGHT = 6.15


def preview_colors(color, brightness, effect="solid", key_colors=None, preview_time=0):
    from lighting import compose

    colors = compose(color, brightness, effect, key_colors)
    if preview_time:
        from effects import TEMPLATES, frame

        if effect in TEMPLATES:
            animated = frame(effect, preview_time, brightness)
            for code in animated:
                if str(code) not in (key_colors or {}):
                    colors[code] = animated[code]
    return [colors.get(key["code"], (0, 0, 0)) for key in KEYS]


def hit_test(px, py, width, height):
    unit = min((width - 12) / WIDTH, (height - 12) / HEIGHT)
    if unit <= 0:
        return None
    x = (px - (width - WIDTH * unit) / 2) / unit
    y = (py - (height - HEIGHT * unit) / 2) / unit
    for key in KEYS:
        left = key["x"] + 0.045
        top = key["y"] + 0.045
        w = key["w"] - 0.09
        h = key["h"] - 0.09
        if not (left <= x <= left + w and top <= y <= top + h):
            continue
        if key["shape"] == "iso-enter" and y > top + 1 and x < left + 0.25:
            continue
        # Respect the rounded corners drawn by Cairo.
        if key["shape"] != "iso-enter":
            cx = min(max(x, left + 0.10), left + w - 0.10)
            cy = min(max(y, top + 0.10), top + h - 0.10)
            if (x - cx) ** 2 + (y - cy) ** 2 > 0.10**2:
                continue
        return key
    return None


# Experimental diagram-to-protocol association; physical RGB addresses
# have not been verified key by key on the GT76.
_codes = {
    **{chr(65 + i): 4 + i for i in range(26)},
    **{str(i): 29 + i for i in range(1, 10)},
    "0": 39,
    **{f"F{i}": 57 + i for i in range(1, 13)},
    "Esc": 41,
    "Retroceso": 42,
    "Tab": 43,
    "Espacio": 44,
    "º ª": 53,
    "' ?": 45,
    "¡ ¿": 46,
    "` ^": 47,
    "+ *": 48,
    "Ñ": 51,
    "´ ¨": 52,
    "Ç": 49,
    "< >": 100,
    ", ;": 54,
    ". :": 55,
    "- _": 56,
    "Bloq Mayús": 57,
    "Impr\nPant": 70,
    "Bloq\nDespl": 71,
    "Pausa": 72,
    "Insert": 73,
    "Inicio": 74,
    "Supr": 76,
    "Fin": 77,
    "→": 79,
    "←": 80,
    "↓": 81,
    "↑": 82,
    "Bloq\nNum": 83,
    "/": 84,
    "*": 85,
    "−": 86,
    "+": 87,
    "7\nInicio": 95,
    "8 ↑": 96,
    "9\nRe Pág": 97,
    "4 ←": 92,
    "6 →": 94,
    "1\nFin": 89,
    "2 ↓": 90,
    "3\nAv Pág": 91,
    "0\nInsert": 98,
    ".\nSupr": 99,
    "Fn": 240,
    "Alt": 226,
    "Alt Gr": 230,
    "Win": 227,
}
for key in KEYS:
    label = key["label"]
    code = _codes.get(label)
    if label == "5" and key["x"] > 16:
        code = 93
    if label == "Intro":
        code = 88 if key["x"] > 16 else 40
    if label == "Mayús":
        code = 225 if key["x"] == 0 else 229
    if label == "Ctrl":
        code = 224 if key["x"] == 0 else 228
    key["code"] = code

# Track physical addresses in the map revision without renumbering user profiles.

for key in KEYS:
    key["rgb_code"] = GT76_RGB_ADDRESSES.get(key["code"], key["code"])


def paint(ctx, width, height, colors=None, selected=None, verification=None):
    unit = min((width - 12) / WIDTH, (height - 12) / HEIGHT)
    ctx.save()
    ctx.translate((width - WIDTH * unit) / 2, (height - HEIGHT * unit) / 2)
    ctx.scale(unit, unit)
    for index, key in enumerate(KEYS):
        rgb = tuple(v / 255 for v in colors[index]) if colors is not None else (0.38, 0.59, 0.82)
        x = key["x"] + 0.045
        y = key["y"] + 0.045
        w = key["w"] - 0.09
        h = key["h"] - 0.09
        ctx.new_path()
        if key["shape"] == "iso-enter":
            ctx.move_to(x, y)
            ctx.line_to(x + w, y)
            ctx.line_to(x + w, y + h)
            ctx.line_to(x + 0.25, y + h)
            ctx.line_to(x + 0.25, y + 1.0)
            ctx.line_to(x, y + 1.0)
            ctx.close_path()
        else:
            r = 0.10
            for cx, cy, start in [
                (x + w - r, y + r, -math.pi / 2),
                (x + w - r, y + h - r, 0),
                (x + r, y + h - r, math.pi / 2),
                (x + r, y + r, math.pi),
            ]:
                ctx.arc(cx, cy, r, start, start + math.pi / 2)
            ctx.close_path()
        ctx.set_source_rgb(*(0.025 + v * 0.23 for v in rgb))
        ctx.fill_preserve()
        is_selected = (
            key["code"] in selected
            if isinstance(selected, (set, frozenset))
            else key["code"] == selected
        )
        ctx.set_source_rgb(*((1, 1, 1) if is_selected else rgb))
        ctx.set_line_width(0.055 if is_selected else 0.022)
        ctx.stroke()
        result = (verification or {}).get(str(key["code"]), {}).get("result")
        if result:
            ctx.new_path()
            ctx.arc(x + w - 0.14, y + 0.14, 0.065, 0, 2 * math.pi)
            ctx.set_source_rgb(*((0.25, 0.95, 0.55) if result == "correct" else (1, 0.60, 0.15)))
            ctx.fill()
        ctx.select_font_face("DejaVu Sans", 0, 0)
        lines = key["label"].split("\n")
        size = 0.235 if len(key["label"]) > 8 and len(lines) == 1 else 0.27
        ctx.set_font_size(size)
        widest = max(ctx.text_extents(line).width for line in lines)
        if widest > w - 0.12:
            size *= (w - 0.12) / widest
        ctx.set_font_size(size)
        for i, line in enumerate(lines):
            ext = ctx.text_extents(line)
            lx = x + (w - ext.width) / 2 - ext.x_bearing
            ly = y + h / 2 + (i - (len(lines) - 1) / 2) * 0.30 + size * 0.34
            ctx.move_to(lx, ly)
            ctx.set_source_rgb(*(0.18 + v * 0.82 for v in rgb))
            ctx.show_text(line)
    ctx.restore()

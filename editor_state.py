"""Desired editor state; unknown hardware state must not masquerade as readback."""

from copy import deepcopy

from color_math import rgb_value
from key_selection import ALL
from lighting import compose


class EditorState:
    def __init__(self, settings):
        self.color = settings["color"]
        self.effect = settings.get("effect", "solid")
        self.key_colors = dict(settings.get("key_colors", {}))
        self.brightness = 100
        self.known = set()
        self.full_known = False

    def set_color(self, codes, color):
        codes = set(codes)
        if not codes or not codes <= ALL:
            raise ValueError("Selecciona una o varias teclas.")
        rgb_value(color, 100)
        if codes == ALL:
            self.color = color
            self.effect = "solid"
            self.key_colors = {}
            self.known = set(ALL)
            self.full_known = True
            return True
        self.key_colors.update({str(code): color for code in codes})
        self.known.update(codes)
        self.full_known = self.known == ALL
        return False

    def set_brightness(self, value):
        if not self.full_known:
            raise ValueError(
                "No se pueden conservar colores que el controlador aún no permite leer. Elige primero un color para todo el teclado, una muestra fija o un perfil."
            )
        rgb_value("#000000", value)
        self.brightness = float(value)

    def load(self, profile):
        rgb_value(profile["color"], profile["brightness"])
        self.color = profile["color"]
        self.brightness = float(profile["brightness"])
        self.effect = profile.get("effect", "solid")
        self.key_colors = dict(profile.get("key_colors", {}))
        self.known = set(ALL)
        self.full_known = True

    def colors(self, brightness=None):
        return compose(
            self.color,
            self.brightness if brightness is None else brightness,
            self.effect,
            self.key_colors,
        )

    def partial_colors(self, codes):
        colors = self.colors()
        return {code: colors[code] for code in codes}

    def snapshot(self):
        return deepcopy(
            {
                "color": self.color,
                "brightness": self.brightness,
                "effect": self.effect,
                "key_colors": self.key_colors,
            }
        )

"""Selection in visual row order, independent of GTK and USB."""

from keyboard_layout import KEYS

ORDER = tuple(key["code"] for key in sorted(KEYS, key=lambda k: (k["y"], k["x"])))
ALL = frozenset(ORDER)


class KeySelection:
    def __init__(self):
        self.codes = set()
        self.anchor = None

    def click(self, code, ctrl=False, shift=False):
        if code not in ALL:
            raise ValueError("Tecla fuera del mapa.")
        if shift and self.anchor is not None:
            a, b = sorted((ORDER.index(self.anchor), ORDER.index(code)))
            span = set(ORDER[a : b + 1])
            self.codes = self.codes | span if ctrl else span
        elif ctrl:
            self.codes.symmetric_difference_update({code})
            self.anchor = code
        else:
            self.codes = {code}
            self.anchor = code
        return set(self.codes)

    def clear(self):
        self.codes.clear()
        self.anchor = None

    def all(self):
        self.codes = set(ALL)

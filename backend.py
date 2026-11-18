"""SteelSeries KLC 1038:1122. Only static-color 0x0E and refresh 0x09 packets."""

import ctypes as C
import ctypes.util
import fcntl
import os
import time
from pathlib import Path

from color_math import rgb_value as rgb_value
from devices import GT76_RGB_ADDRESSES, active_keyboard
from vendor.keycodes import REGION_KEYCODES
from vendor.msiprotocol import make_key_colors_packet, make_refresh_packet


class Keyboard:
    def __enter__(self):
        # Serialize the complete open/write/refresh/close transaction across
        # GUI instances and login restoration; never interleave region packets.
        runtime = Path(os.environ.get("XDG_RUNTIME_DIR", str(Path.home() / ".cache"))) / "titan-rgb"
        runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock = (runtime / "keyboard.lock").open("a")
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.lock.close()
            raise RuntimeError(
                "Otro envío está en curso. Espera a que termine antes de aplicar."
            ) from None
        try:
            return self._open()
        except BaseException:
            self.lock.close()
            raise

    def _open(self):
        device = active_keyboard()
        path = ctypes.util.find_library("hidapi-hidraw")
        if not path:
            raise RuntimeError(
                "Falta HIDAPI con backend hidraw (libhidapi-hidraw; en Debian/Ubuntu: libhidapi-hidraw0)."
            )
        lib = self.lib = C.CDLL(path)
        lib.hid_init.argtypes = []
        lib.hid_init.restype = C.c_int
        lib.hid_open_path.argtypes = [C.c_char_p]
        lib.hid_open_path.restype = C.c_void_p
        for method in ("hid_send_feature_report", "hid_write"):
            fn = getattr(lib, method)
            fn.argtypes = [C.c_void_p, C.c_char_p, C.c_size_t]
            fn.restype = C.c_int
        lib.hid_close.argtypes = [C.c_void_p]
        lib.hid_close.restype = None
        lib.hid_error.argtypes = [C.c_void_p]
        lib.hid_error.restype = C.c_wchar_p
        if lib.hid_init() != 0:
            raise RuntimeError("No se ha podido iniciar HIDAPI.")
        self.dev = lib.hid_open_path(os.fsencode(device.path))
        if not self.dev:
            raise RuntimeError(
                "No se puede abrir el teclado. Comprueba la conexión y los permisos de acceso."
            )
        return self

    def frame(self, colors, refresh=True):
        # Validate the complete frame before sending anything.
        packets = []
        for region, keys in REGION_KEYCODES.items():
            mapping = {}
            for key in keys:
                if key == 0:
                    continue
                logical = next(
                    (source for source, target in GT76_RGB_ADDRESSES.items() if target == key), key
                )
                rgb = colors[logical]
                if (
                    not isinstance(rgb, (list, tuple))
                    or len(rgb) != 3
                    or any(type(v) is not int or not 0 <= v <= 255 for v in rgb)
                ):
                    raise ValueError("Fotograma RGB inválido.")
                mapping[key] = list(rgb)
            packet = bytes(make_key_colors_packet(region, mapping))
            if len(packet) != 524 or packet[0] != 0x0E:
                raise ValueError("Paquete estático inválido.")
            packets.append((region, packet))
        for region, data in packets:
            if self.lib.hid_send_feature_report(self.dev, data, len(data)) != len(data):
                raise RuntimeError(
                    "Fallo USB en el bloque "
                    + region
                    + ". La iluminación puede haber quedado parcial. "
                    + (self.lib.hid_error(self.dev) or "Envío incompleto.")
                )
            time.sleep(0.02)
        if refresh:
            data = bytes(make_refresh_packet())
            if self.lib.hid_write(self.dev, data, len(data)) != len(data):
                raise RuntimeError(
                    "Fallo USB al actualizar. La iluminación puede haber quedado parcial. "
                    + (self.lib.hid_error(self.dev) or "Envío incompleto.")
                )
            # Upstream also waits after the output report before closing HID.
            time.sleep(0.02)

    def set_keys(self, colors):
        # Same validated static format, restricted to the selected addresses.
        supported = {key for keys in REGION_KEYCODES.values() for key in keys if key}
        if (
            not colors
            or any(type(code) is not int for code in colors)
            or not set(colors) <= supported
        ):
            raise ValueError("Selección de teclas inválida.")
        translated = {GT76_RGB_ADDRESSES.get(code, code): rgb for code, rgb in colors.items()}
        if len(translated) != len(colors):
            raise ValueError("La selección contiene direcciones RGB duplicadas.")
        colors = translated
        packets = []
        for region, keys in REGION_KEYCODES.items():
            mapping = {}
            for key in keys:
                if key not in colors:
                    continue
                rgb = colors[key]
                if (
                    not isinstance(rgb, (list, tuple))
                    or len(rgb) != 3
                    or any(type(value) is not int or not 0 <= value <= 255 for value in rgb)
                ):
                    raise ValueError("Color de tecla inválido.")
                mapping[key] = list(rgb)
            if mapping:
                packets.append((region, bytes(make_key_colors_packet(region, mapping))))
        for region, data in packets:
            if self.lib.hid_send_feature_report(self.dev, data, len(data)) != len(data):
                raise RuntimeError(
                    "Fallo USB en " + region + ". El cambio puede haber quedado parcial."
                )
            time.sleep(0.02)
        data = bytes(make_refresh_packet())
        if self.lib.hid_write(self.dev, data, len(data)) != len(data):
            raise RuntimeError("No se pudo actualizar la selección.")
        time.sleep(0.02)

    def __exit__(self, *_):
        try:
            self.lib.hid_close(self.dev)
        finally:
            self.lock.close()


def apply_color(color, brightness):
    rgb = rgb_value(color, brightness)
    with Keyboard() as keyboard:
        keyboard.frame({k: rgb for keys in REGION_KEYCODES.values() for k in keys})

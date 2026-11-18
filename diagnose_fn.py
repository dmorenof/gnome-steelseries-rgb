#!/usr/bin/python3
"""Read-only, bounded Fn diagnostic. Never grabs devices or writes USB/EC."""

import os
import select
import struct
import time
from pathlib import Path

EVENT = struct.Struct("@llHHi")
NAMES = {"AT Translated Set 2 keyboard", "SteelSeries SteelSeries KLC", "MSI WMI hotkeys"}
KEYS = {
    74: "− numérico",
    78: "+ numérico",
    228: "alternar iluminación",
    229: "bajar iluminación",
    230: "subir iluminación",
}


def main():
    devices = {}
    try:
        for entry in Path("/sys/class/input").glob("event*"):
            name = (entry / "device/name").read_text().strip()
            if name not in NAMES:
                continue
            try:
                fd = os.open("/dev/input/" + entry.name, os.O_RDONLY | os.O_NONBLOCK)
            except PermissionError:
                print(
                    "Sin permiso de lectura para " + name + ". Ejecuta este diagnóstico con sudo."
                )
                return 1
            devices[fd] = name
        if not devices:
            print("No se encontraron los dispositivos esperados.")
            return 1
        print("Preparado. En los próximos 30 segundos pulsa Fn + −, espera, y Fn + +.", flush=True)
        print(
            "Solo se muestran teclas de iluminación y +/− numéricos; otras señales se cuentan sin guardar su contenido.",
            flush=True,
        )
        other = {name: 0 for name in devices.values()}
        end = time.monotonic() + 30
        while time.monotonic() < end:
            ready, _, _ = select.select(
                list(devices), [], [], min(1, max(0, end - time.monotonic()))
            )
            for fd in ready:
                data = os.read(fd, EVENT.size * 64)
                for offset in range(0, len(data) - EVENT.size + 1, EVENT.size):
                    _, _, kind, code, value = EVENT.unpack_from(data, offset)
                    if kind == 1 and code in KEYS:
                        print(
                            devices[fd]
                            + ": "
                            + KEYS[code]
                            + " · "
                            + {0: "soltar", 1: "pulsar", 2: "repetir"}.get(value, "otro"),
                            flush=True,
                        )
                    elif kind not in (0,):
                        other[devices[fd]] += 1
        print("Fin. Otras señales (solo cantidades): " + str(other))
        return 0
    finally:
        for fd in devices:
            os.close(fd)


if __name__ == "__main__":
    raise SystemExit(main())

"""Experimental static color adapter for selected SteelSeries keyboards.
Only SDK metadata queries and UpdateLEDs are used. No device scan, mode,
firmware, hardware brightness, or persistent device configuration commands.
"""

import fcntl
import hashlib
import json
import os
import socket
import struct
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from color_math import rgb_value
from devices import identify_devices
from openrgb_discovery import HEADER, _request


class Reader:
    def __init__(self, data):
        self.data = data
        self.offset = 0

    def take(self, size):
        if size < 0 or self.offset + size > len(self.data):
            raise ValueError("Descripción OpenRGB incompleta.")
        result = self.data[self.offset : self.offset + size]
        self.offset += size
        return result

    def number(self, fmt):
        return struct.unpack("<" + fmt, self.take(struct.calcsize("<" + fmt)))[0]

    def text(self):
        size = self.number("H")
        if not 1 <= size <= 4096:
            raise ValueError("Cadena OpenRGB inválida.")
        raw = self.take(size)
        if raw[-1:] != b"\0":
            raise ValueError("Cadena OpenRGB sin terminador.")
        if b"\0" in raw[:-1]:
            raise ValueError("Cadena OpenRGB con terminador interno.")
        return "".join(c for c in raw[:-1].decode("utf-8") if c.isprintable())


@dataclass(frozen=True)
class Mode:
    name: str
    flags: int
    color_mode: int


@dataclass(frozen=True)
class Zone:
    name: str
    kind: int
    count: int


@dataclass(frozen=True)
class Snapshot:
    id: str
    layout_id: str
    name: str
    description: str
    version: str
    leds: tuple
    colors: tuple
    modes: tuple
    active_mode: int
    zones: tuple
    duplicate_direct: bool = False
    mode_signature: str = ""

    @property
    def writable(self):
        return (
            not self.duplicate_direct
            and bool(self.leds)
            and 0 <= self.active_mode < len(self.modes)
            and bool(self.modes[self.active_mode].flags & 32)
            and self.modes[self.active_mode].color_mode == 1
        )

    @property
    def reason(self):
        if self.duplicate_direct:
            return "El GT76 se controla por su adaptador directo; acceso duplicado bloqueado."
        if not self.writable:
            return "Requiere un modo activo de colores por LED, por ejemplo Direct en OpenRGB."
        return "Control estático experimental. Un LED puede representar una tecla o una zona; pendiente de comprobación física."


def parse_snapshot(data, direct_available=False, direct_paths=()):
    reader = Reader(data)
    if reader.number("I") != len(data):
        raise ValueError("Tamaño OpenRGB inválido.")
    kind = reader.number("i")
    if kind != 5:
        return None
    name, description, version, serial, location = (reader.text() for _ in range(5))
    # This release targets SteelSeries. Generic keyboards remain identification only.
    if "steelseries" not in (name + " " + description).lower():
        return None
    mode_start = reader.offset
    mode_count = reader.number("H")
    active = reader.number("i")
    if mode_count > 256:
        raise ValueError("Demasiados modos OpenRGB.")
    modes = []
    for _ in range(mode_count):
        mode_name = reader.text()
        value, flags, speed_min, speed_max, colors_min, colors_max, speed, direction, color_mode = (
            struct.unpack("<9I", reader.take(36))
        )
        count = reader.number("H")
        if count > 4096:
            raise ValueError("Demasiados colores de modo.")
        reader.take(count * 4)
        modes.append(Mode(mode_name, flags, color_mode))
    mode_signature = hashlib.sha256(data[mode_start : reader.offset]).hexdigest()
    zone_maps = []
    zones = []
    zone_count = reader.number("H")
    if zone_count > 256:
        raise ValueError("Demasiadas zonas OpenRGB.")
    for _ in range(zone_count):
        zone_name = reader.text()
        zone_kind, minimum, maximum, count = struct.unpack("<4I", reader.take(16))
        if count > 4096:
            raise ValueError("Zona demasiado grande.")
        matrix_size = reader.number("H")
        matrix = reader.take(matrix_size)
        if matrix:
            if len(matrix) < 8:
                raise ValueError("Matriz OpenRGB incompleta.")
            height, width = struct.unpack_from("<II", matrix)
            if height * width > 16384 or len(matrix) != 8 + height * width * 4:
                raise ValueError("Matriz OpenRGB inválida.")
        zone_maps.append((zone_name, zone_kind, minimum, maximum, count, matrix.hex()))
        zones.append(Zone(zone_name, zone_kind, count))
    led_count = reader.number("H")
    if not 1 <= led_count <= 4096:
        raise ValueError("Cantidad de LED no válida.")
    leds = []
    led_values = []
    for _ in range(led_count):
        leds.append(reader.text())
        led_values.append(reader.number("I"))
    color_count = reader.number("H")
    if color_count != led_count or sum(z.count for z in zones) != led_count:
        raise ValueError("El mapa OpenRGB no coincide con sus colores.")
    colors = tuple(tuple(reader.take(4)[:3]) for _ in range(color_count))
    if reader.offset != len(data):
        raise ValueError("Descripción OpenRGB con datos inesperados.")
    map_data = json.dumps(
        {"leds": leds, "values": led_values, "zones": zone_maps}, ensure_ascii=False
    ).encode()
    map_hash = hashlib.sha256(map_data).hexdigest()
    # Persist only a digest; serial/location are not logged, exported or displayed.
    identity = hashlib.sha256(
        json.dumps([name, description, version, serial, location]).encode()
    ).hexdigest()
    duplicate = direct_available and (
        any(p in location for p in direct_paths)
        or any(
            token in (name + " " + description + " " + location).lower()
            for token in ("1122", "klc", "gt76", "msi")
        )
    )
    return Snapshot(
        "openrgb:" + identity,
        "openrgb-leds:" + map_hash,
        name,
        description,
        version,
        tuple(leds),
        colors,
        tuple(modes),
        active,
        tuple(zones),
        duplicate,
        mode_signature,
    )


def _snapshots(sock, deadline):
    data = _request(sock, 0, 0, b"", deadline)
    if len(data) != 4:
        raise ValueError("Cantidad de dispositivos inválida.")
    count = struct.unpack("<I", data)[0]
    if count > 128:
        raise ValueError("Demasiados dispositivos OpenRGB.")
    direct = [device for device in identify_devices() if device.supported]
    results = []
    for index in range(count):
        raw = _request(sock, index, 1, struct.pack("<I", 0), deadline)
        parsed = parse_snapshot(raw, bool(direct), tuple(d.path for d in direct))
        if parsed is not None:
            results.append((index, parsed))
    return results


def discover_controls(port=6742, timeout=4):
    deadline = time.monotonic() + timeout
    with socket.create_connection(("127.0.0.1", port), timeout) as sock:
        return [snapshot for _, snapshot in _snapshots(sock, deadline)]


def compose_colors(colors, brightness):
    result = []
    for color in colors:
        result.append(tuple(rgb_value(color, brightness)))
    if not 1 <= len(result) <= 4096:
        raise ValueError("Cantidad de colores inválida.")
    return tuple(result)


@contextmanager
def _lock():
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", str(Path.home() / ".cache"))) / "titan-rgb"
    runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (runtime / "keyboard.lock").open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Hay otro envío en curso.") from None
        yield


def apply_colors(expected, hex_colors, brightness, port=6742, timeout=4, *, indices=None):
    colors = compose_colors(hex_colors, brightness)
    if len(colors) != len(expected.leds):
        raise ValueError("Los colores no coinciden con el dispositivo.")
    if indices is not None:
        indices = frozenset(indices)
        if not indices or any(type(i) is not int or not 0 <= i < len(colors) for i in indices):
            raise ValueError("Selección OpenRGB inválida.")
    deadline = time.monotonic() + timeout
    with _lock(), socket.create_connection(("127.0.0.1", port), timeout) as sock:
        matches = [
            (index, snapshot)
            for index, snapshot in _snapshots(sock, deadline)
            if snapshot.id == expected.id
        ]
        if len(matches) != 1:
            raise RuntimeError(
                "El teclado cambió, se desconectó o su identidad es ambigua. Vuelve a consultar dispositivos."
            )
        index, current = matches[0]
        if current.layout_id != expected.layout_id:
            raise RuntimeError("El mapa del teclado cambió. No se enviaron colores.")
        if not current.writable:
            raise RuntimeError(current.reason)
        if (
            current.active_mode != expected.active_mode
            or current.modes != expected.modes
            or current.mode_signature != expected.mode_signature
        ):
            raise RuntimeError("El modo del teclado cambió. Vuelve a consultar dispositivos.")
        if indices is not None:
            colors = tuple(
                rgb if i in indices else current.colors[i] for i, rgb in enumerate(colors)
            )
        # Protocol 0 UpdateLEDs: payload size includes itself, u16 count, RGBX.
        payload = struct.pack("<IH", 6 + len(colors) * 4, len(colors)) + b"".join(
            bytes((*rgb, 0)) for rgb in colors
        )
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("La consulta caducó antes del envío.")
        sock.settimeout(remaining)
        sock.sendall(HEADER.pack(b"ORGB", index, 1050, len(payload)) + payload)
        # SDK v0 has no acknowledgement for UpdateLEDs. Report only socket delivery.
    return colors

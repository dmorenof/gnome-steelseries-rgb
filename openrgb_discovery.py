"""Optional local SDK discovery. Only controller count/data requests are allowed.
Protocol reference: OpenRGB NetworkProtocol.h and RGBController serialization.
Independent minimal implementation; no OpenRGB code or dependencies are bundled.
"""

import socket
import struct
import time
from dataclasses import dataclass

HEADER = struct.Struct("<4sIII")
MAX_SIZE = 8 * 1024 * 1024


@dataclass(frozen=True)
class RemoteKeyboard:
    name: str
    description: str
    version: str


def _receive(sock, size, deadline):
    result = bytearray()
    while len(result) < size:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("OpenRGB no respondió a tiempo.")
        sock.settimeout(remaining)
        chunk = sock.recv(size - len(result))
        if not chunk:
            raise ConnectionError("OpenRGB cerró la conexión.")
        result.extend(chunk)
    return bytes(result)


def _request(sock, device, command, payload, deadline):
    if command not in (0, 1):
        raise ValueError("Esta conexión solo permite consultar dispositivos.")
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("OpenRGB no respondió a tiempo.")
    sock.settimeout(remaining)
    sock.sendall(HEADER.pack(b"ORGB", device, command, len(payload)) + payload)
    for _ in range(16):
        magic, dev, cmd, size = HEADER.unpack(_receive(sock, HEADER.size, deadline))
        if magic != b"ORGB" or size > MAX_SIZE:
            raise ValueError("Respuesta OpenRGB inválida.")
        data = _receive(sock, size, deadline)
        if dev == device and cmd == command:
            return data
        if cmd != 100:
            raise ValueError("Respuesta OpenRGB inesperada.")
    raise ValueError("Demasiadas notificaciones OpenRGB.")


def parse_keyboard(data):
    # Version 0: size u32, type i32, then name/description/version/serial/location.
    if len(data) < 8:
        raise ValueError("Descripción OpenRGB incompleta.")
    size, kind = struct.unpack_from("<Ii", data)
    if size != len(data):
        raise ValueError("Tamaño de descripción OpenRGB inválido.")
    offset = 8
    fields = []
    for _ in range(5):
        if offset + 2 > len(data):
            raise ValueError("Cadena OpenRGB incompleta.")
        length = struct.unpack_from("<H", data, offset)[0]
        offset += 2
        if not 1 <= length <= 4096 or offset + length > len(data):
            raise ValueError("Cadena OpenRGB inválida.")
        raw = data[offset : offset + length]
        offset += length
        if raw[-1:] != b"\0":
            raise ValueError("Cadena OpenRGB sin terminador.")
        value = raw[:-1].decode("utf-8", errors="replace")
        fields.append("".join(ch for ch in value if ch.isprintable()))
    if kind != 5:
        return None
    # No serial numbers or hardware paths are retained or displayed.
    return RemoteKeyboard(*fields[:3])


def discover(port=6742, timeout=3.0):
    deadline = time.monotonic() + timeout
    result = []
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as sock:
        count_data = _request(sock, 0, 0, b"", deadline)
        if len(count_data) != 4:
            raise ValueError("Cantidad OpenRGB inválida.")
        count = struct.unpack("<I", count_data)[0]
        if count > 128:
            raise ValueError("Demasiados dispositivos OpenRGB.")
        for index in range(count):
            # Request protocol 0 explicitly; no handshake or modes are changed.
            data = _request(sock, index, 1, struct.pack("<I", 0), deadline)
            keyboard = parse_keyboard(data)
            if keyboard is not None:
                result.append(keyboard)
    return result

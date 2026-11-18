import socket
import struct
import tempfile
import threading
import time
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import openrgb_control as control
import remote_profiles
from openrgb_discovery import HEADER, _receive


def text(value):
    raw = value.encode() + b"\0"
    return struct.pack("<H", len(raw)) + raw


def description(name="SteelSeries test", serial="a", leds=("A", "B", "C"), flags=32, color_mode=1):
    data = struct.pack("<i", 5) + b"".join(
        text(value) for value in (name, "keyboard", "1.0", serial, "HID test path")
    )
    data += (
        struct.pack("<Hi", 1, 0)
        + text("Direct")
        + struct.pack("<9IH", 0, flags, 0, 0, 0, 0, 0, 0, color_mode, 0)
    )
    data += (
        struct.pack("<H", 1)
        + text("Keyboard")
        + struct.pack("<4IH", 2, len(leds), len(leds), len(leds), 0)
    )
    data += struct.pack("<H", len(leds))
    for i, name in enumerate(leds):
        data += text(name) + struct.pack("<I", i)
    data += struct.pack("<H", len(leds)) + bytes((10, 20, 30, 0)) * len(leds)
    return struct.pack("<I", len(data) + 4) + data


class Server:
    def __init__(self, descriptions):
        self.descriptions = descriptions
        self.requests = []
        self.errors = []
        self.server = socket.socket()
        self.server.bind(("127.0.0.1", 0))
        self.server.listen(1)
        self.server.settimeout(3)
        self.port = self.server.getsockname()[1]

    def __enter__(self):
        def serve():
            try:
                with self.server:
                    conn, _ = self.server.accept()
                    with conn:
                        while True:
                            try:
                                raw = _receive(conn, 16, time.monotonic() + 3)
                            except ConnectionError:
                                return
                            magic, index, command, length = HEADER.unpack(raw)
                            payload = _receive(conn, length, time.monotonic() + 3)
                            self.requests.append((index, command, payload))
                            if command == 1050:
                                return
                            if command == 0:
                                data = struct.pack("<I", len(self.descriptions))
                            elif command == 1:
                                data = self.descriptions[index]
                            else:
                                raise AssertionError("Unexpected command")
                            reply = HEADER.pack(b"ORGB", index, command, len(data)) + data
                            conn.sendall(reply[:5])
                            conn.sendall(reply[5:])
            except Exception as error:
                self.errors.append(error)

        self.thread = threading.Thread(target=serve, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.thread.join(4)
        if self.errors:
            raise self.errors[0]


class ControlTests(unittest.TestCase):
    def test_complete_metadata_and_capabilities(self):
        snapshot = control.parse_snapshot(description())
        self.assertTrue(snapshot.writable)
        self.assertEqual(snapshot.leds, ("A", "B", "C"))
        self.assertEqual(snapshot.colors, ((10, 20, 30),) * 3)
        self.assertNotIn("HID test path", repr(snapshot))
        self.assertEqual(snapshot.zones[0].count, 3)
        self.assertFalse(control.parse_snapshot(description(flags=0)).writable)
        self.assertFalse(control.parse_snapshot(description(color_mode=2)).writable)
        self.assertIsNone(control.parse_snapshot(description(name="another manufacturer")))

    def test_duplicate_gt76_is_not_writable(self):
        snapshot = control.parse_snapshot(
            description(name="SteelSeries MSI KLC"), True, ("/dev/hidraw3",)
        )
        self.assertTrue(snapshot.duplicate_direct)
        self.assertFalse(snapshot.writable)

    def test_reordered_list_is_resolved_by_identity_not_saved_index(self):
        expected = control.parse_snapshot(description(serial="chosen"))
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.dict("os.environ", {"XDG_RUNTIME_DIR": tmp}),
            patch("openrgb_control.identify_devices", return_value=[]),
            Server([description(serial="other"), description(serial="chosen")]) as server,
        ):
            colors = control.apply_colors(
                expected, ["#ff0000", "#00ff00", "#0000ff"], 50, server.port
            )
        self.assertEqual(colors, ((128, 0, 0), (0, 128, 0), (0, 0, 128)))
        index, command, payload = server.requests[-1]
        self.assertEqual((index, command), (1, 1050))
        self.assertEqual(struct.unpack_from("<IH", payload), (18, 3))
        self.assertEqual(payload[6:], bytes((128, 0, 0, 0, 0, 128, 0, 0, 0, 0, 128, 0)))
        self.assertTrue(all(command in (0, 1, 1050) for _, command, _ in server.requests))

    def test_changes_fail_before_any_color_packet(self):
        expected = control.parse_snapshot(description())
        for remote in (
            description(leds=("A", "different", "C")),
            description(flags=0),
            description(serial="replaced"),
        ):
            with (
                tempfile.TemporaryDirectory() as tmp,
                patch.dict("os.environ", {"XDG_RUNTIME_DIR": tmp}),
                patch("openrgb_control.identify_devices", return_value=[]),
                Server([remote]) as server,
            ):
                with self.assertRaises(RuntimeError):
                    control.apply_colors(expected, ["#ffffff"] * 3, 100, server.port)
            self.assertFalse(any(command == 1050 for _, command, _ in server.requests))

    def test_partial_update_preserves_latest_server_colors(self):
        expected = control.parse_snapshot(description())
        remote = description()[:-12] + bytes((1, 2, 3, 0, 4, 5, 6, 0, 7, 8, 9, 0))
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.dict("os.environ", {"XDG_RUNTIME_DIR": tmp}),
            patch("openrgb_control.identify_devices", return_value=[]),
            Server([remote]) as server,
        ):
            result = control.apply_colors(
                expected, ["#ffffff", "#ff0000", "#ffffff"], 50, server.port, indices={1}
            )
        self.assertEqual(result, ((1, 2, 3), (128, 0, 0), (7, 8, 9)))
        self.assertEqual(
            server.requests[-1][2],
            struct.pack("<IH", 18, 3) + bytes((1, 2, 3, 0, 128, 0, 0, 0, 7, 8, 9, 0)),
        )

    def test_numeric_led_address_change_invalidates_map(self):
        original = description()
        expected = control.parse_snapshot(original)
        changed = bytearray(original)
        # The final LED's numeric address immediately precedes color_count.
        struct.pack_into("<I", changed, len(changed) - 18, 999)
        current = control.parse_snapshot(bytes(changed))
        self.assertNotEqual(expected.layout_id, current.layout_id)
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.dict("os.environ", {"XDG_RUNTIME_DIR": tmp}),
            patch("openrgb_control.identify_devices", return_value=[]),
            Server([bytes(changed)]) as server,
        ):
            with self.assertRaisesRegex(RuntimeError, "mapa del teclado cambió"):
                control.apply_colors(expected, ["#ffffff"] * 3, 100, server.port)
        self.assertFalse(any(command == 1050 for _, command, _ in server.requests))

    def test_switch_between_writable_modes_prevents_update(self):
        expected = control.parse_snapshot(description())
        remote = description().replace(b"Direct", b"Custom")
        self.assertTrue(control.parse_snapshot(remote).writable)
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.dict("os.environ", {"XDG_RUNTIME_DIR": tmp}),
            patch("openrgb_control.identify_devices", return_value=[]),
            Server([remote]) as server,
        ):
            with self.assertRaisesRegex(RuntimeError, "modo del teclado cambió"):
                control.apply_colors(expected, ["#ffffff"] * 3, 100, server.port)
        self.assertFalse(any(command == 1050 for _, command, _ in server.requests))

    def test_ambiguous_identity_is_rejected(self):
        expected = control.parse_snapshot(description())
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.dict("os.environ", {"XDG_RUNTIME_DIR": tmp}),
            patch("openrgb_control.identify_devices", return_value=[]),
            Server([description(), description()]) as server,
        ):
            with self.assertRaises(RuntimeError):
                control.apply_colors(expected, ["#ffffff"] * 3, 100, server.port)
        self.assertFalse(any(command == 1050 for _, command, _ in server.requests))

    def test_corrupt_data_and_invalid_color_rejected(self):
        for raw in (b"", description()[:-1], description() + b"\0"):
            with self.assertRaises((ValueError, struct.error)):
                control.parse_snapshot(raw)
        with self.assertRaises(ValueError):
            control.compose_colors(["#ff0000", "bad"], 100)
        self.assertEqual(control.compose_colors(["#ffffff"], 0), ((0, 0, 0),))

    def test_profiles_bound_to_led_map_and_preserve_original_store(self):
        snapshot = control.parse_snapshot(description())
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("remote_profiles.path", return_value=Path(tmp) / "profiles.json"),
        ):
            remote_profiles.put(snapshot, "test", ["#ff0000"] * 3, 75)
            self.assertEqual(remote_profiles.get(snapshot, "test"), (["#ff0000"] * 3, 75))
            with self.assertRaises(ValueError):
                remote_profiles.get(replace(snapshot, layout_id="wrong"), "test")
            original = remote_profiles.path().read_bytes()
            with self.assertRaises(ValueError):
                remote_profiles.put(snapshot, "invalid", ["bad"] * 3, 75)
            self.assertEqual(original, remote_profiles.path().read_bytes())
            remote_profiles.delete(snapshot, "test")
            self.assertEqual(remote_profiles.names(snapshot), [])
            remote_profiles.path().write_text("broken")
            before = remote_profiles.path().read_bytes()
            with self.assertRaises(RuntimeError):
                remote_profiles.put(snapshot, "test", ["#ffffff"] * 3, 100)
            self.assertEqual(remote_profiles.path().read_bytes(), before)


if __name__ == "__main__":
    unittest.main()

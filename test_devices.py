import json
import socket
import struct
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import app
import openrgb_discovery as sdk
import session_restore
from backend import Keyboard
from devices import GT76_ID, GT76_LAYOUT, KLC_DESCRIPTOR, Capabilities, Device, identify_devices
from profile_binding import export_profile, import_profile, validate_target

DEVICE = Device(
    GT76_ID, "KLC", "/dev/fake", "msi-klc", True, "tested", Capabilities(True, True, True)
)


class DeviceTests(unittest.TestCase):
    def fixture(self, root, product="GT76 Titan DT 9SF", descriptor=None):
        root = Path(root)
        dmi = root / "class/dmi/id"
        dmi.mkdir(parents=True)
        for name, value in [
            ("sys_vendor", "Micro-Star International Co., Ltd."),
            ("product_name", product),
            ("board_name", "MS-17H1"),
        ]:
            (dmi / name).write_text(value)
        node = root / "class/hidraw/hidraw3/device"
        node.mkdir(parents=True)
        (node / "uevent").write_text("HID_ID=0003:00001038:00001122\nHID_NAME=KLC\n")
        (node / "report_descriptor").write_bytes(
            descriptor if descriptor is not None else KLC_DESCRIPTOR
        )
        return root

    def test_identifier_alone_does_not_enable_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.fixture(tmp, product="Another MSI laptop")
            self.assertFalse(identify_devices(root)[0].supported)
            (root / "class/dmi/id/product_name").write_text("GT76 Titan DT 9SF")
            self.assertTrue(identify_devices(root)[0].supported)
            (root / "class/hidraw/hidraw3/device/report_descriptor").write_bytes(b"input interface")
            self.assertFalse(identify_devices(root)[0].supported)

    def test_unsupported_device_does_not_open_hid(self):
        with (
            patch("backend.active_keyboard", side_effect=RuntimeError("unsupported")),
            patch("backend.C.CDLL") as library,
        ):
            with self.assertRaises(RuntimeError):
                Keyboard()._open()
            library.assert_not_called()

    def test_portable_profile_preserves_colors_and_rejects_incompatible_files(self):
        profile = {
            "color": "#004488",
            "brightness": 40,
            "effect": "Aqua",
            "key_colors": {"74": "#ff0000", "77": "#00ff00"},
            "device_id": GT76_ID,
            "layout_id": GT76_LAYOUT,
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "profile.json"
            export_profile(path, "Noche", profile)
            self.assertEqual(import_profile(path), ("Noche", profile))
            original = path.read_bytes()
            with self.assertRaises(FileExistsError):
                export_profile(path, "Otro", profile)
            self.assertEqual(path.read_bytes(), original)
            data = json.loads(original)
            for change in (
                {"layout_id": "other"},
                {"key_colors": {"0": "#ff0000"}},
                {"brightness": True},
            ):
                path.write_text(json.dumps({**data, "profile": {**profile, **change}}))
                with self.assertRaises(ValueError):
                    import_profile(path)

    def test_profile_binding_refuses_other_device_and_layout(self):
        validate_target({}, DEVICE)  # Legacy profiles still work on the verified model.
        for data in ({"device_id": "another-keyboard"}, {"layout_id": "ansi-us"}):
            with self.assertRaises(ValueError):
                validate_target(data, DEVICE)

    def test_schema_migration_preserves_original_and_binding(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(app, "CONFIG", Path(tmp) / "settings.json"),
        ):
            original = {
                "color": "#ffffff",
                "brightness": 60,
                "profiles": {"work": {"color": "#ff0000", "brightness": 100}},
                "key_colors": {"4": "#00ff00"},
            }
            app.CONFIG.write_text(json.dumps(original))
            saved = app.CONFIG.read_bytes()
            loaded = app.load()
            app.save(loaded)
            self.assertEqual((app.CONFIG.parent / "settings.before-v2.json").read_bytes(), saved)
            self.assertEqual(app.load()["profiles"]["work"]["device_id"], GT76_ID)
            self.assertEqual(app.load()["key_colors"], original["key_colors"])
            app.CONFIG.write_text('{"schema_version":999}')
            with self.assertRaises(RuntimeError):
                app.load()

    def test_restore_retries_access_and_records_only_transport(self):
        settings = {
            "autostart": True,
            "color": "#ff0000",
            "brightness": 100,
            "key_colors": {"4": "#00ff00"},
        }
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.dict("os.environ", {"XDG_STATE_HOME": tmp}),
            patch(
                "session_restore.active_keyboard", side_effect=[RuntimeError("not ready"), DEVICE]
            ),
            patch("session_restore.time.sleep"),
            patch("session_restore.engine.stop"),
            patch("session_restore.apply_lighting") as send,
        ):
            self.assertTrue(session_restore.restore(settings))
            send.assert_called_once_with("#ff0000", 100, "solid", {"4": "#00ff00"})
            result = session_restore.read_status()
            self.assertEqual(result["result"], "usb-transmitted")
            self.assertFalse(result["visual_confirmation"])
            self.assertEqual(result["attempts"], 2)

    def test_restore_wrong_profile_sends_nothing(self):
        settings = {"autostart": True, "device_id": "wrong"}
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.dict("os.environ", {"XDG_STATE_HOME": tmp}),
            patch("session_restore.active_keyboard", return_value=DEVICE),
            patch("session_restore.apply_lighting") as send,
        ):
            with self.assertRaises(ValueError):
                session_restore.restore(settings)
            send.assert_not_called()
            self.assertEqual(session_restore.read_status()["result"], "failed")

    def test_log_failure_does_not_repeat_usb(self):
        settings = {"autostart": True, "color": "#ffffff", "brightness": 100}
        with (
            patch("session_restore.active_keyboard", return_value=DEVICE),
            patch("session_restore.engine.stop"),
            patch("session_restore.apply_lighting") as send,
            patch("session_restore._write_record", side_effect=OSError("full")),
        ):
            self.assertTrue(session_restore.restore(settings))
            send.assert_called_once()


class SDKTests(unittest.TestCase):
    def description(self, kind=5):
        payload = struct.pack("<i", kind)
        for value in ("SteelSeries example", "keyboard", "1.0", "private serial", "private path"):
            raw = value.encode() + b"\0"
            payload += struct.pack("<H", len(raw)) + raw
        return struct.pack("<I", len(payload) + 4) + payload

    def test_parser_filters_nonkeyboards_and_rejects_malformed_sizes(self):
        keyboard = sdk.parse_keyboard(self.description())
        self.assertEqual(keyboard.name, "SteelSeries example")
        self.assertNotIn("private", repr(keyboard))
        self.assertIsNone(sdk.parse_keyboard(self.description(0)))
        for data in (b"", self.description()[:12], b"\0\0\0\0" + self.description()[4:]):
            with self.assertRaises(ValueError):
                sdk.parse_keyboard(data)

    def test_local_server_receives_only_discovery_requests(self):
        requests = []
        errors = []
        server = socket.socket()
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        server.settimeout(3)

        def serve():
            try:
                with server:
                    conn, _ = server.accept()
                    with conn:
                        conn.settimeout(3)
                        for _ in range(3):
                            deadline = __import__("time").monotonic() + 2
                            magic, device, command, length = sdk.HEADER.unpack(
                                sdk._receive(conn, 16, deadline)
                            )
                            payload = sdk._receive(conn, length, deadline)
                            requests.append((device, command, payload))
                            data = (
                                struct.pack("<I", 2)
                                if command == 0
                                else self.description(5 if device == 0 else 0)
                            )
                            packet = sdk.HEADER.pack(b"ORGB", device, command, len(data)) + data
                            # Deliberately fragmented TCP responses.
                            conn.sendall(packet[:7])
                            conn.sendall(packet[7:])
            except Exception as error:
                errors.append(error)

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        found = sdk.discover(port=server.getsockname()[1])
        thread.join(3)
        self.assertFalse(errors)
        self.assertEqual(len(found), 1)
        self.assertEqual(
            requests, [(0, 0, b""), (0, 1, struct.pack("<I", 0)), (1, 1, struct.pack("<I", 0))]
        )

    def test_write_commands_rejected_without_socket(self):
        with self.assertRaises(ValueError):
            sdk._request(None, 0, 1050, b"", 0)


if __name__ == "__main__":
    unittest.main()

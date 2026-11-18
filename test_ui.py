"""Opt-in GTK integration checks with temporary storage and mocked device writes.
Run with TITAN_RGB_UI_TESTS=1 under a display, or dbus-run-session and Xvfb.
"""

import os
import tempfile
import threading
import time
import unittest
import uuid
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import gi

gi.require_versions({"Gtk": "4.0", "Gdk": "4.0"})
from gi.repository import Gdk, Gio, GLib, Gtk

import app
from devices import GT76_ID, Capabilities, Device
from map_verification import Verification
from openrgb_control import parse_snapshot
from openrgb_window import OpenRGBWindow
from settings import DEFAULT, SettingsStore
from storage import StorageError
from test_openrgb_control import description

DEVICE = Device(
    GT76_ID, "Test KLC", "/dev/test", "msi-klc", True, "simulated", Capabilities(True, True, True)
)


@unittest.skipUnless(
    os.environ.get("TITAN_RGB_UI_TESTS") == "1", "GTK integration tests are opt-in"
)
class GTKTests(unittest.TestCase):
    def setUp(self):
        if not Gtk.init_check():
            self.skipTest("A graphical display is required")
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.config = Path(self.folder.name) / "settings.json"
        for context in (
            patch.object(app, "CONFIG", self.config),
            patch.object(app, "identify_devices", return_value=[DEVICE]),
            patch.object(app, "active_keyboard", return_value=DEVICE),
            patch.object(
                app,
                "detect_layout",
                return_value={
                    "sources": [["xkb", "es"]],
                    "source": "GNOME",
                    "diagram": "gt76-es-iso",
                },
            ),
            patch.object(app.engine, "stop"),
            patch.object(app, "read_status", return_value={}),
            patch.object(
                app,
                "Verification",
                side_effect=lambda: Verification(Path(self.folder.name) / "map.json"),
            ),
        ):
            context.start()
            self.addCleanup(context.stop)
        keyboard_patch = patch.object(app, "Keyboard")
        self.keyboard = keyboard_patch.start()
        self.addCleanup(keyboard_patch.stop)
        full_patch = patch.object(app, "apply_lighting")
        self.full = full_patch.start()
        self.addCleanup(full_patch.stop)

    def create_app(self):
        ui = app.App()
        ui.set_application_id("local.steelseries.rgb.test.t" + uuid.uuid4().hex)
        ui.set_flags(Gio.ApplicationFlags.NON_UNIQUE)
        self.assertTrue(ui.register(None))
        self.assertFalse(ui.get_is_remote())
        ui.activate()
        self.addCleanup(ui.quit)
        self.addCleanup(ui.get_active_window().destroy)
        self.addCleanup(ui.shutdown_editor)
        return ui

    def wait_for(self, condition):
        deadline = time.monotonic() + 3
        while not condition():
            if time.monotonic() > deadline:
                self.fail("GTK callback did not finish")
            GLib.MainContext.default().iteration(False)
            time.sleep(0.005)

    def test_startup_selection_and_invalid_hex_do_not_write(self):
        ui = self.create_app()
        self.assertTrue(ui.brightness.get_sensitive())
        self.assertIsNone(ui.live_timer)
        ui.select_key(74)
        ui.hex_entry.set_text("#XXXXXX")
        self.assertFalse(ui.dirty_codes)
        self.keyboard.assert_not_called()
        self.full.assert_not_called()
        self.assertFalse(self.config.exists())
        ui.hex_entry.set_text("#00FF00")
        ui.flush_pending()
        self.keyboard.return_value.__enter__.return_value.set_keys.assert_called_once_with(
            {74: (0, 153, 0)}
        )
        self.assertEqual(SettingsStore(self.config).load()["key_colors"]["74"], "#00ff00")

    def test_failed_usb_can_be_retried_and_is_not_saved_as_success(self):
        ui = self.create_app()
        self.keyboard.return_value.__enter__.side_effect = RuntimeError("access denied")
        ui.select_key(4)
        ui.pick("#ff0000")
        ui.flush_pending()
        self.assertTrue(ui.retry_button.get_visible())
        self.assertEqual(ui.dirty_codes, {4})
        self.assertFalse(self.config.exists())
        self.keyboard.return_value.__enter__.side_effect = None
        ui.flush_pending()
        self.assertFalse(ui.retry_button.get_visible())
        self.assertFalse(ui.dirty_codes)
        self.assertEqual(SettingsStore(self.config).load()["key_colors"]["4"], "#ff0000")

    def test_settings_failure_after_usb_reports_delivery_without_retrying_usb(self):
        ui = self.create_app()
        ui.select_key(4)
        ui.pick("#ff0000")
        with patch.object(app, "save", side_effect=StorageError("disk failure")):
            ui.flush_pending()
        self.keyboard.return_value.__enter__.return_value.set_keys.assert_called_once()
        self.assertFalse(ui.dirty_codes)
        self.assertFalse(ui.retry_button.get_visible())
        self.assertIn("Cambio transmitido por USB, pero no se pudo guardar", ui.status.get_text())
        self.assertFalse(self.config.exists())

    def test_external_settings_change_prevents_stale_usb_write(self):
        ui = self.create_app()
        other = SettingsStore(self.config)
        data = other.load()
        data["color"] = "#0000ff"
        other.save(data)
        ui.select_key(4)
        ui.pick("#ff0000")
        ui.flush_pending()
        self.keyboard.assert_not_called()
        self.full.assert_not_called()
        self.assertEqual(SettingsStore(self.config).load()["color"], "#0000ff")
        self.assertTrue(ui.retry_button.get_visible())

    def test_corrupt_settings_show_error_without_editor_or_writes(self):
        self.config.write_text("{broken")
        ui = self.create_app()
        self.assertIsNotNone(ui.startup_error)
        self.assertFalse(hasattr(ui, "brightness"))
        self.keyboard.assert_not_called()
        self.full.assert_not_called()
        self.assertEqual(self.config.read_text(), "{broken")

    def test_off_state_can_recover_after_reopening(self):
        data = deepcopy(DEFAULT)
        data.update(brightness=0, resume_brightness=75, key_colors={"4": "#ff0000"})
        store = SettingsStore(self.config)
        store.load()
        store.save(data)
        ui = self.create_app()
        self.assertEqual(ui.off.get_label(), "Recuperar iluminación")
        self.full.assert_not_called()
        ui.turn_off()
        ui.flush_pending()
        self.assertEqual(ui.editor.brightness, 75)
        self.assertEqual(ui.editor.key_colors, {"4": "#ff0000"})
        self.full.assert_called_once()

    def test_profile_management_preserves_configuration_and_does_not_write_usb(self):
        ui = self.create_app()
        ui.editor.set_color({4}, "#ff0000")
        ui.name.set_text("Work")
        ui.profile_save()
        ui.name.set_text("Evening")
        ui.profile_rename()
        target = Path(self.folder.name) / "profile.json"
        with patch.object(
            ui, "profile_file", side_effect=lambda title, action, callback, *_: callback(target)
        ):
            ui.profile_export()
            ui.profile_delete()
            ui.profile_import()
        stored = SettingsStore(self.config).load()
        self.assertEqual(stored["profiles"]["Evening"]["key_colors"], {"4": "#ff0000"})
        self.keyboard.assert_not_called()
        self.full.assert_not_called()

    def test_remote_sender_serializes_edits_and_finishes_after_close(self):
        ui = self.create_app()
        release = threading.Event()
        calls = []

        def send(snapshot, colors, brightness, *, indices):
            calls.append((colors, brightness, indices))
            if len(calls) == 1 and not release.wait(3):
                raise RuntimeError("test timeout")

        with (
            patch("openrgb_window.apply_colors", side_effect=send),
            patch("remote_profiles.names", return_value=[]),
        ):
            window = OpenRGBWindow(ui, parse_snapshot(description()))
            self.addCleanup(window.destroy)
            self.addCleanup(window.shutdown_sender)
            window.flow.select_child(window.flow.get_child_at_index(0))
            self.assertEqual(calls, [])
            rgba = Gdk.RGBA()
            rgba.parse("#ff0000")
            window.color.set_rgba(rgba)
            window.selection_color()
            self.wait_for(lambda: len(calls) == 1)
            window.flow.unselect_all()
            window.flow.select_child(window.flow.get_child_at_index(2))
            rgba.parse("#00ff00")
            window.color.set_rgba(rgba)
            window.selection_color()
            window.flush_on_close()
            release.set()
            self.wait_for(lambda: len(calls) == 2 and not window.busy)
            self.assertEqual(calls[0][2], {0})
            self.assertEqual(calls[1][2], {2})
            self.assertEqual(calls[1][0][2], "#00ff00")

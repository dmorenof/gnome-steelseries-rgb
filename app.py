#!/usr/bin/python3
import argparse
import json
import sys
import threading
from pathlib import Path

import engine
from backend import Keyboard, rgb_value
from devices import GT76_ID, GT76_LAYOUT, active_keyboard, identify_devices
from editor_state import EditorState
from effects import TEMPLATES
from key_selection import KeySelection
from lighting import apply_lighting
from map_verification import Verification, key_name
from profile_binding import binding, export_profile, import_profile, profile_name, validate_target
from session_restore import read_status
from session_restore import restore as restore_session
from version import APP_VERSION

CONFIG = Path.home() / ".config/titan-rgb/settings.json"
BASE = Path(__file__).resolve().parent
from settings import DEFAULT, SettingsStore
from storage import StorageError

_settings_store = None


def settings_store():
    global _settings_store
    if _settings_store is None or _settings_store.path != CONFIG:
        _settings_store = SettingsStore(CONFIG)
    return _settings_store


def load():
    return settings_store().load()


def save(data):
    settings_store().save(data)


def autostart(enabled):
    from desktop_integration import set_autostart

    set_autostart(enabled, BASE)


def command_arguments():
    parser = argparse.ArgumentParser(description="SteelSeries RGB Controller GNOME")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--version", action="store_true", help="Print the application version.")
    group.add_argument(
        "--list-devices", action="store_true", help="List device metadata without applying colors."
    )
    group.add_argument("--restore", action="store_true", help="Run opt-in login restoration.")
    group.add_argument(
        "--smoke",
        action="store_true",
        help="Open and close an isolated UI without applying colors.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = command_arguments()
    if arguments.version:
        print(APP_VERSION)
        raise SystemExit(0)
    if arguments.list_devices:
        print(
            json.dumps(
                [device.summary() for device in identify_devices()], ensure_ascii=False, indent=2
            )
        )
        raise SystemExit(0)
    if arguments.restore:
        try:
            restore_session(load())
        except (OSError, RuntimeError, ValueError) as error:
            print(str(error), file=sys.stderr)
            raise SystemExit(1) from None
        raise SystemExit(0)

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk

gi.require_foreign("cairo")
from keyboard_layout import KEYS as DIAGRAM_KEYS
from keyboard_layout import hit_test, preview_colors
from keyboard_layout import paint as paint_keyboard
from layout_detection import describe_layout, detect_layout


class App(Gtk.Application):
    def __init__(self, smoke=False):
        self.smoke = smoke
        self.closing = False
        super().__init__(
            application_id="local.steelseries.rgb.smoke"
            if "--smoke" in sys.argv
            else "local.steelseries.rgb"
        )
        self._ready = False
        self._updating_widgets = False
        self.live_timer = None
        self.dirty_codes = set()
        self.full_pending = False
        self.selection = KeySelection()
        self.pre_off = None
        self.verification = Verification()
        self.verification_states = {}
        self.preview_time = 0
        self.preview_timer = None
        self.preview_started = 0
        self.connect("shutdown", lambda *_: self.shutdown_editor())
        self.startup_error = None
        try:
            self.settings = load()
        except StorageError as error:
            from copy import deepcopy

            self.settings = deepcopy(DEFAULT)
            self.startup_error = str(error)
        self.editor = EditorState(self.settings)
        self.editor.load(self.settings)
        if self.editor.brightness == 0:
            self.pre_off = {
                **self.editor.snapshot(),
                "brightness": self.settings["resume_brightness"],
            }
        self.preview_effect = self.settings["effect"]
        self.key_colors = dict(self.settings["key_colors"])
        self.selected_key = None
        self.layout = detect_layout()
        self.devices = identify_devices()
        self.device = next((d for d in self.devices if d.supported), None)
        self.connect("activate", self.activate)

    def activate(self, *_):
        if self.get_active_window():
            self.get_active_window().present()
            return
        Gtk.Settings.get_default().set_property("gtk-application-prefer-dark-theme", True)
        css = Gtk.CssProvider()
        css.load_from_data(b"""
        window { background: #11151e; color: #edf2ff; }
        .hero { font-size: 32px; font-weight: 800; }
        .subtle { color: #9caac2; }
        .card { background: #1c2331; border-radius: 18px; padding: 20px; }
        .section { font-weight: 700; font-size: 16px; }
        .preview { border-radius: 14px; background: #111722; padding: 18px; }
        .key { border-radius: 5px; border: 1px solid #4a698d; padding: 5px; background: #202d40; }
        button { border-radius: 9px; min-height: 28px; }
        .suggested-action { background: #82b5ff; color: #102035; font-weight: 700; }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        win = Gtk.ApplicationWindow(
            application=self,
            title="SteelSeries RGB Controller GNOME",
            default_width=1040,
            default_height=820,
        )
        if self.startup_error:
            message = Gtk.Label(label=self.startup_error, wrap=True)
            message.set_margin_start(24)
            message.set_margin_end(24)
            win.set_child(message)
            win.present()
            if self.smoke:
                GLib.timeout_add(1200, lambda: self.quit() or False)
            return
        scroll = Gtk.ScrolledWindow()
        win.set_child(scroll)
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        for side in ("top", "bottom", "start", "end"):
            getattr(root, "set_margin_" + side)(26)
        scroll.set_child(root)
        root.append(self.label("SteelSeries RGB Controller GNOME", "hero"))
        root.append(self.label("Controlador independiente de iluminación para GNOME", "subtle"))
        card = self.card(root)
        card.append(
            self.label(
                self.device.name if self.device else "Teclado sin controlador compatible", "section"
            )
        )
        device_info = self.label(
            self.device.reason
            if self.device
            else "Solo se identifican dispositivos; no se envían colores a modelos sin validar.",
            "subtle",
        )
        device_info.set_wrap(True)
        card.append(device_info)
        preview = self.preview = Gtk.DrawingArea()
        preview.set_content_width(600)
        preview.set_content_height(295)
        preview.set_hexpand(True)
        preview.add_css_class("preview")
        preview.set_draw_func(
            lambda area, ctx, width, height: paint_keyboard(
                ctx,
                width,
                height,
                self.display_colors(),
                self.selection.codes,
                self.verification_states,
            )
        )
        preview.set_tooltip_text(
            "Clic: seleccionar · Ctrl: añadir/quitar · Mayús: rango · Ctrl+A: todo · Esc: limpiar"
        )
        preview.set_focusable(True)
        keyboard = Gtk.EventControllerKey()
        keyboard.connect("key-pressed", self.selection_key)
        preview.add_controller(keyboard)
        click = Gtk.GestureClick()
        click.set_button(1)
        click.connect("released", self.key_clicked)
        preview.add_controller(click)
        card.append(preview)
        card.append(self.label(describe_layout(self.layout), "subtle"))
        preview.set_visible(self.device is not None and self.layout["diagram"] == "gt76-es-iso")
        note = self.label(
            "Clic selecciona · Ctrl añade o quita · Mayús selecciona un rango. El color se aplica a la selección.",
            "subtle",
        )
        note.set_wrap(True)
        card.append(note)
        self.selection_status = self.label("Ninguna tecla seleccionada.", "subtle")
        card.append(self.selection_status)
        self.readback_status = self.label(
            "Estado actual del teclado: desconocido. No se han leído sus colores.", "subtle"
        )
        self.readback_status.set_wrap(True)
        card.append(self.readback_status)
        verification = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        details = Gtk.Expander(label="Comprobar el mapa de teclas")
        details.set_child(verification)
        card.append(details)
        self.verify_mode = Gtk.CheckButton(
            label="Comprobar la correspondencia de las teclas al cambiar su color"
        )
        self.verify_mode.set_sensitive(self.device is not None)
        verification.append(self.verify_mode)
        self.verification_progress = self.label("", "subtle")
        self.verification_progress.set_wrap(True)
        verification.append(self.verification_progress)
        verification.append(
            self.label(
                "Verde: confirmada · naranja: incidencia · sin punto: pendiente. Solo se registra tu comprobación visual.",
                "subtle",
            )
        )
        export = Gtk.Button(label="Guardar informe del mapa")
        export.connect("clicked", self.export_verification)
        verification.append(export)
        self.refresh_verification()
        controls = self.card(root)
        controls.append(self.label("Color de las teclas seleccionadas", "section"))
        row = Gtk.Box(spacing=16)
        controls.append(row)
        row.append(self.label("Color"))
        self.color = Gtk.ColorButton()
        self.color.set_use_alpha(False)
        self.set_color(self.settings["color"])
        row.append(self.color)
        self.hex_entry = Gtk.Entry(placeholder_text="#RRGGBB", width_chars=9, max_width_chars=9)
        self.hex_entry.set_max_length(7)
        self.hex_entry.set_tooltip_text(
            "Escribe un color completo, por ejemplo #00CCAA. Se aplica automáticamente a la selección."
        )
        self.hex_entry.connect("changed", self.hex_changed)
        row.append(self.hex_entry)
        self.hex = self.label("Selecciona teclas", "subtle")
        self.hex.set_wrap(True)
        controls.append(self.hex)
        self.color.connect("color-set", lambda *_: self.color_changed())
        palette = self.palette = Gtk.Box(spacing=7)
        controls.append(palette)
        for name, color in [
            ("Hielo", "#64a8ff"),
            ("Rojo", "#ff4055"),
            ("Violeta", "#ae77ff"),
            ("Verde", "#53e6a4"),
            ("Blanco", "#ffffff"),
        ]:
            b = Gtk.Button(label=name)
            b.connect("clicked", lambda _, c=color: self.pick(c))
            palette.append(b)
        buttons = Gtk.Box(spacing=10)
        controls.append(buttons)
        all_button = Gtk.Button(label="Seleccionar todo")
        all_button.connect("clicked", lambda *_: self.select_all())
        buttons.append(all_button)
        clear = Gtk.Button(label="Limpiar selección")
        clear.connect("clicked", lambda *_: self.clear_selection())
        buttons.append(clear)
        intensity = self.card(root)
        intensity.append(self.label("Intensidad de los colores", "section"))
        row = Gtk.Box(spacing=12)
        intensity.append(row)
        row.append(self.label("Intensidad RGB"))
        self.brightness = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.brightness.set_value(self.editor.brightness)
        self.brightness.set_hexpand(True)
        self.brightness.set_digits(0)
        row.append(self.brightness)
        self.brightness.connect("value-changed", self.brightness_changed)
        self.brightness.set_tooltip_text(
            "Escala los colores enviados. El brillo interno del teclado se ajusta por separado."
        )
        self.intensity_note = self.label("", "subtle")
        self.intensity_note.set_wrap(True)
        intensity.append(self.intensity_note)
        hardware_note = self.label(
            "Brillo del teclado: control manual · Fn + − del numérico para subirlo."
            if self.device
            else "El brillo interno depende del modelo y aún no está disponible.",
            "subtle",
        )
        hardware_note.set_wrap(True)
        intensity.append(hardware_note)
        self.off = Gtk.Button(label="Apagar")
        self.off.connect("clicked", lambda *_: self.turn_off())
        intensity.append(self.off)
        self.status = self.label(
            "Último ajuste cargado en la interfaz. No se ha enviado iluminación al abrir.", "subtle"
        )
        self.status.set_wrap(True)
        intensity.append(self.status)
        self.retry_button = Gtk.Button(label="Reintentar envío")
        self.retry_button.set_visible(False)
        self.retry_button.connect("clicked", lambda *_: self.flush_pending())
        intensity.append(self.retry_button)
        restored = read_status()
        if restored.get("result") == "failed":
            self.status.set_text(
                "Falló la última restauración al iniciar sesión: "
                + restored.get("error", "error desconocido")
            )
        templates = self.card(root)
        templates.append(self.label("Muestras de las plantillas", "section"))
        templates.append(
            self.label(
                "En el teclado: muestras fijas. La reproducción animada de abajo solo afecta al dibujo.",
                "subtle",
            )
        )
        row = Gtk.Box(spacing=10)
        templates.append(row)
        self.templates = Gtk.DropDown(
            model=Gtk.StringList.new(["Elige una muestra fija…"] + list(TEMPLATES))
        )
        self.templates.set_hexpand(True)
        row.append(self.templates)
        self.description = self.label(TEMPLATES["Plain"], "subtle")
        self.description.set_wrap(True)
        templates.append(self.description)
        self.templates.connect("notify::selected", lambda *_: self.template_changed())

        self.preview_animation = Gtk.CheckButton(label="Reproducir la recreación solo en pantalla")
        self.preview_animation.set_sensitive(False)
        self.preview_animation.connect("toggled", self.toggle_preview)
        templates.append(self.preview_animation)
        templates.append(
            self.label(
                "Elegir una muestra envía una sola imagen fija. La reproducción animada solo modifica el dibujo.",
                "subtle",
            )
        )
        profiles = self.card(root)
        profiles.append(self.label("Tus perfiles", "section"))
        row = Gtk.Box(spacing=10)
        profiles.append(row)
        self.names = Gtk.StringList.new([])
        self.dropdown = Gtk.DropDown(model=self.names)
        self.dropdown.set_hexpand(True)
        row.append(self.dropdown)
        b = Gtk.Button(label="Cargar")
        b.connect("clicked", lambda *_: self.profile_load())
        row.append(b)
        b = Gtk.Button(label="Eliminar")
        b.connect("clicked", lambda *_: self.profile_delete())
        row.append(b)
        row = Gtk.Box(spacing=10)
        profiles.append(row)
        self.name = Gtk.Entry(
            placeholder_text="Nombre para crear o renombrar", hexpand=True, max_length=60
        )
        row.append(self.name)
        b = Gtk.Button(label="Crear perfil")
        b.connect("clicked", lambda *_: self.profile_save())
        row.append(b)
        b = Gtk.Button(label="Renombrar seleccionado")
        b.connect("clicked", self.profile_rename)
        row.append(b)
        row = Gtk.Box(spacing=10)
        profiles.append(row)
        for label, callback in [
            ("Importar…", self.profile_import),
            ("Exportar seleccionado…", self.profile_export),
        ]:
            button = Gtk.Button(label=label)
            button.connect("clicked", callback)
            row.append(button)
        self.profile_status = self.label("", "subtle")
        self.profile_status.set_wrap(True)
        profiles.append(self.profile_status)
        self.refresh_profiles()
        discovery_box = self.card(root)
        discovery = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        discovery_details = Gtk.Expander(label="Otros teclados · OpenRGB experimental")
        discovery_details.set_child(discovery)
        discovery_box.append(discovery_details)
        self.remote_snapshots = []
        self.remote_windows = {}
        self.discovery_status = self.label(
            "OpenRGB opcional · detectar no cambia la iluminación. Los controles adicionales son experimentales.",
            "subtle",
        )
        self.discovery_status.set_wrap(True)
        discovery.append(self.discovery_status)
        self.discover_button = Gtk.Button(label="Consultar teclados en OpenRGB")
        self.discover_button.connect("clicked", self.discover_openrgb)
        discovery.append(self.discover_button)
        self.remote_select = Gtk.DropDown(model=Gtk.StringList.new([]))
        discovery.append(self.remote_select)
        self.open_remote_button = Gtk.Button(label="Abrir controles del teclado seleccionado")
        self.open_remote_button.set_sensitive(False)
        self.open_remote_button.connect("clicked", self.open_remote)
        discovery.append(self.open_remote_button)
        self.auto = Gtk.CheckButton(
            label="Aplicar mi ajuste guardado al iniciar sesión (sustituye la iluminación existente)"
        )
        self.auto.set_tooltip_text(
            "Desactivado: la aplicación no envía colores al iniciar sesión. Activado: reemplaza el estado del teclado, incluido el dejado por Windows."
        )
        self.auto.set_active(bool(self.settings["autostart"]))
        self.auto.connect("toggled", self.toggle_auto)
        root.append(self.auto)
        root.append(
            self.label(
                "Versión "
                + APP_VERSION
                + " · proyecto independiente · sin soporte oficial de MSI ni SteelSeries",
                "subtle",
            )
        )
        self._ready = True
        self.sync_editor()
        win.connect("close-request", lambda *_: self.close_editor())
        win.present()
        if self.smoke:
            GLib.timeout_add(1200, lambda: self.quit() or False)

    def label(self, text, style=None):
        x = Gtk.Label(label=text, xalign=0)
        if style:
            x.add_css_class(style)
        return x

    def card(self, parent):
        x = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        x.add_css_class("card")
        parent.append(x)
        return x

    def stop_preview(self):
        if hasattr(self, "preview_animation") and self.preview_animation.get_active():
            self.preview_animation.set_active(False)
            return
        if self.preview_timer is not None:
            GLib.source_remove(self.preview_timer)
            self.preview_timer = None
        self.preview_time = 0
        if hasattr(self, "preview"):
            self.preview.queue_draw()

    def toggle_preview(self, button):
        if not button.get_active():
            self.stop_preview()
            return
        if self.preview_effect not in TEMPLATES or self.preview_effect == "Plain":
            self.stop_preview()
            return
        self.preview_started = GLib.get_monotonic_time() / 1000000
        self.preview_timer = GLib.timeout_add(33, self.preview_tick)

    def preview_tick(self):
        if not self.preview_animation.get_active():
            self.preview_timer = None
            return False
        self.preview_time = GLib.get_monotonic_time() / 1000000 - self.preview_started
        self.preview.queue_draw()
        return True

    def refresh_verification(self):
        try:
            self.verification_states = self.verification.states()
            good = sum(value["result"] == "correct" for value in self.verification_states.values())
            problems = len(self.verification_states) - good
            self.verification_progress.set_text(
                f"Mapa GT76: {good}/102 teclas confirmadas · {problems} con incidencias."
            )
        except RuntimeError as error:
            self.verification_progress.set_text(str(error))
        self.preview.queue_draw()

    def confirm_key(self, key):
        dialog = Gtk.Dialog(
            title="Comprobar " + key_name(key), transient_for=self.get_active_window(), modal=True
        )
        dialog.add_button("Sin comprobar", Gtk.ResponseType.CANCEL)
        dialog.add_button("Guardar observación", Gtk.ResponseType.OK)
        content = dialog.get_content_area()
        content.set_spacing(12)
        for side in ("top", "bottom", "start", "end"):
            getattr(content, "set_margin_" + side)(18)
        content.append(
            Gtk.Label(
                label="Mira el teclado físico: ¿cambió únicamente la tecla " + key_name(key) + "?",
                wrap=True,
            )
        )
        answers = Gtk.DropDown(
            model=Gtk.StringList.new(
                [
                    "Elige una respuesta…",
                    "Sí, solo esa tecla",
                    "Cambió otra tecla o varias",
                    "No se aprecia el cambio",
                ]
            )
        )
        # No success answer is preselected: confirmation must be deliberate.
        answers.set_selected(0)
        content.append(answers)
        note = Gtk.Entry(placeholder_text="Observación opcional: qué tecla cambió")
        note.set_max_length(240)
        content.append(note)
        save_button = dialog.get_widget_for_response(Gtk.ResponseType.OK)
        save_button.set_sensitive(False)
        answers.connect(
            "notify::selected",
            lambda *_: save_button.set_sensitive(1 <= answers.get_selected() <= 3),
        )

        def response(dialog, result):
            if result == Gtk.ResponseType.OK and 1 <= answers.get_selected() <= 3:
                try:
                    self.verification.record(
                        key["code"],
                        ("correct", "different", "no-change")[answers.get_selected() - 1],
                        note.get_text(),
                    )
                    self.refresh_verification()
                except (RuntimeError, OSError, ValueError) as error:
                    self.verification_progress.set_text(str(error))
            dialog.destroy()

        dialog.connect("response", response)
        dialog.present()

    def export_verification(self, *_):
        dialog = Gtk.FileChooserNative(
            title="Guardar informe del mapa",
            transient_for=self.get_active_window(),
            action=Gtk.FileChooserAction.SAVE,
            accept_label="Guardar",
            cancel_label="Cancelar",
        )
        dialog.set_current_name("gt76-comprobacion-mapa.json")

        def response(dialog, result):
            if result == Gtk.ResponseType.ACCEPT:
                try:
                    target = dialog.get_file().get_path()
                    if not target:
                        raise ValueError("Elige un archivo local.")
                    Path(target).write_text(
                        json.dumps(self.verification.report(), ensure_ascii=False, indent=2)
                    )
                    self.verification_progress.set_text(
                        "Informe guardado. No contiene perfiles, colores ni números de serie."
                    )
                except (RuntimeError, OSError, ValueError) as error:
                    self.verification_progress.set_text(str(error))
            dialog.destroy()

        dialog.connect("response", response)
        dialog.show()

    def discover_openrgb(self, *_):
        self.discover_button.set_sensitive(False)
        self.discovery_status.set_text("Consultando el servidor local de OpenRGB…")

        def run():
            found = []
            try:
                from openrgb_control import discover_controls

                found = discover_controls()
                message = (
                    (
                        "Teclados SteelSeries encontrados: "
                        + str(len(found))
                        + ". Selecciona uno para consultar sus controles."
                    )
                    if found
                    else "OpenRGB no ha comunicado teclados SteelSeries con un mapa compatible."
                )
            except ConnectionRefusedError:
                message = "El servidor local de OpenRGB no está activo. Esta opción es independiente del control del GT76."
            except Exception as error:
                message = "No se pudo consultar OpenRGB: " + str(error)

            def finish():
                if self.closing:
                    return False
                self.remote_snapshots = found
                self.remote_select.set_model(Gtk.StringList.new([d.name for d in found]))
                self.open_remote_button.set_sensitive(bool(found))
                self.discovery_status.set_text(message)
                self.discover_button.set_sensitive(True)
                return False

            GLib.idle_add(finish)

        threading.Thread(target=run, daemon=True).start()

    def open_remote(self, *_):
        index = self.remote_select.get_selected()
        if not 0 <= index < len(self.remote_snapshots):
            return
        from openrgb_window import OpenRGBWindow

        snapshot = self.remote_snapshots[index]
        key = (snapshot.id, snapshot.layout_id, snapshot.active_mode, snapshot.mode_signature)
        if key not in self.remote_windows:
            self.remote_windows[key] = OpenRGBWindow(self, snapshot)
        self.remote_windows[key].present()

    def set_color(self, color):
        rgba = Gdk.RGBA()
        rgba.parse(color)
        self.color.set_rgba(rgba)

    def hex_changed(self, entry):
        if not self._ready or self._updating_widgets:
            return
        text = entry.get_text().strip()
        try:
            rgb_value(text, 100)
        except ValueError:
            if len(text) == 7:
                entry.add_css_class("error")
            else:
                entry.remove_css_class("error")
            return
        entry.remove_css_class("error")
        self.pick(text.lower())

    def get_color(self):
        c = self.color.get_rgba()
        return "#" + "".join(f"{round(v * 255):02x}" for v in (c.red, c.green, c.blue))

    def shutdown_editor(self):
        self.closing = True
        self.stop_preview()
        if self.live_timer is not None:
            GLib.source_remove(self.live_timer)
            self.live_timer = None

    def close_editor(self):
        self.closing = True
        self.flush_pending()
        self.stop_preview()
        for window in self.remote_windows.values():
            window.flush_on_close()
        return False

    def display_colors(self):
        values = preview_colors(
            self.editor.color,
            self.editor.brightness,
            self.editor.effect,
            self.editor.key_colors,
            self.preview_time,
        )
        return [
            rgb if key["code"] in self.editor.known else (72, 78, 88)
            for key, rgb in zip(DIAGRAM_KEYS, values)
        ]

    def sync_editor(self):
        self.preview_effect = self.editor.effect
        self.key_colors = self.editor.key_colors
        self._updating_widgets = True
        try:
            self.brightness.set_value(self.editor.brightness)
            selected = self.selection.codes
            self.color.set_sensitive(bool(selected) and self.device is not None)
            self.palette.set_sensitive(bool(selected) and self.device is not None)
            self.hex_entry.set_sensitive(bool(selected) and self.device is not None)
            self.hex_entry.remove_css_class("error")
            self.hex_entry.set_text("")
            self.hex_entry.set_placeholder_text("#RRGGBB")
            self.brightness.set_sensitive(self.editor.full_known and self.device is not None)
            self.off.set_sensitive(self.editor.full_known and self.device is not None)
            self.off.set_label("Recuperar iluminación" if self.editor.brightness == 0 else "Apagar")
            if len(selected) == 1:
                key = next(key for key in DIAGRAM_KEYS if key["code"] in selected)
                selection_text = "Tecla seleccionada: " + key_name(key)
            else:
                selection_text = (
                    str(len(selected)) + " teclas seleccionadas."
                    if selected
                    else "Ninguna tecla seleccionada."
                )
            self.selection_status.set_text(selection_text)
            self.intensity_note.set_text(
                "Ajusta en todo el teclado los colores de la muestra. Si otra aplicación cambió la iluminación, este ajuste la sustituirá."
                if self.editor.full_known
                else "Elige una configuración de colores para ajustar su intensidad."
            )
            if selected and selected <= self.editor.known:
                raw_colors = self.editor.colors(100)
                colors = {raw_colors[code] for code in selected}
                if len(colors) == 1:
                    color = "#" + "".join(f"{v:02x}" for v in next(iter(colors)))
                    self.set_color(color)
                    self.hex.set_text("Color de la selección")
                    self.hex_entry.set_text(color.upper())
                else:
                    self.hex.set_text(
                        "La selección contiene varios colores. Elegir uno los sustituye solo en las teclas seleccionadas."
                    )
                    self.hex_entry.set_placeholder_text("Mixto")
            else:
                self.hex.set_text(
                    "Color actual sin leer. El nuevo color se aplicará solo a la selección."
                    if selected
                    else "Selecciona una tecla en el dibujo o pulsa Seleccionar todo."
                )
            if hasattr(self, "description"):
                self.description.set_text(
                    TEMPLATES.get(self.editor.effect, "Color de las teclas seleccionadas.")
                )
            self.preview_animation.set_sensitive(
                self.editor.full_known
                and self.preview_effect in TEMPLATES
                and self.preview_effect != "Plain"
                and self.device is not None
                and self.layout["diagram"] == "gt76-es-iso"
            )
            if self.editor.full_known:
                self.readback_status.set_text(
                    "Muestra del ajuste guardado o editado en la aplicación; no es una lectura de la iluminación actual."
                )
            else:
                self.readback_status.set_text(
                    f"Estado sin leer: {len(self.editor.known)}/102 teclas con color elegido. Gris significa desconocido. La intensidad RGB global requiere una configuración completa."
                )
        finally:
            self._updating_widgets = False
        self.preview.queue_draw()

    def select_key(self, code, ctrl=False, shift=False):
        self.selection.click(code, ctrl, shift)
        self.sync_editor()

    def select_all(self):
        self.selection.all()
        self.sync_editor()
        self.preview.grab_focus()

    def clear_selection(self):
        self.selection.clear()
        self.sync_editor()

    def selection_key(self, controller, keyval, keycode, state):
        if keyval in (Gdk.KEY_a, Gdk.KEY_A) and state & Gdk.ModifierType.CONTROL_MASK:
            self.select_all()
            return True
        if keyval == Gdk.KEY_Escape:
            self.clear_selection()
            return True
        return False

    def key_clicked(self, gesture, count, x, y):
        self.preview.grab_focus()
        key = hit_test(x, y, self.preview.get_width(), self.preview.get_height())
        state = gesture.get_current_event_state() if gesture is not None else 0
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        shift = bool(state & Gdk.ModifierType.SHIFT_MASK)
        if key is None:
            if not ctrl and not shift:
                self.clear_selection()
            return
        self.select_key(key["code"], ctrl, shift)

    def color_changed(self):
        if not self._ready or self._updating_widgets or not self.selection.codes:
            return
        self.stop_preview()
        self.pre_off = None
        color = self.get_color()
        full = self.editor.set_color(self.selection.codes, color)
        self.sync_editor()
        self.schedule_update(full=full, codes=self.selection.codes)

    def pick(self, color):
        self.set_color(color)
        self.color_changed()

    def brightness_changed(self, *_):
        if not self._ready or self._updating_widgets:
            return
        try:
            self.editor.set_brightness(round(self.brightness.get_value()))
        except ValueError as error:
            self.status.set_text(str(error))
            self.sync_editor()
            return
        self.stop_preview()
        self.sync_editor()
        self.schedule_update(full=True)

    def template_changed(self):
        if not self._ready or self._updating_widgets:
            return
        index = self.templates.get_selected()
        if not 1 <= index <= len(TEMPLATES):
            return
        self.stop_preview()
        self.pre_off = None
        effect = list(TEMPLATES)[index - 1]
        self.editor.load(
            {
                "color": self.editor.color,
                "brightness": self.editor.brightness,
                "effect": effect,
                "key_colors": {},
            }
        )
        self.description.set_text(TEMPLATES[effect])
        self.sync_editor()
        self.schedule_update(full=True)

    def schedule_update(self, full=False, codes=()):
        if self.device is None:
            return
        self.full_pending = self.full_pending or full
        self.dirty_codes.update(codes)
        if self.live_timer is not None:
            GLib.source_remove(self.live_timer)
        self.live_timer = GLib.timeout_add(180, self.flush_pending)
        self.status.set_text("Cambio preparado; envío automático al terminar de ajustar.")

    def flush_pending(self):
        if self.live_timer is not None:
            GLib.source_remove(self.live_timer)
            self.live_timer = None
        if not self.full_pending and not self.dirty_codes:
            return False
        full = self.full_pending
        codes = set(self.dirty_codes)
        self.full_pending = False
        self.dirty_codes.clear()
        try:
            settings_store().check_revision()
            device = active_keyboard()
            validate_target(self.settings, device)
            engine.stop()
            if full:
                apply_lighting(
                    self.editor.color,
                    self.editor.brightness,
                    self.editor.effect,
                    self.editor.key_colors,
                )
            else:
                with Keyboard() as keyboard:
                    keyboard.set_keys(self.editor.partial_colors(codes))
        except Exception as error:
            self.full_pending = self.full_pending or full
            self.dirty_codes.update(codes)
            self.retry_button.set_visible(True)
            self.status.set_text("No se pudo transmitir el cambio: " + str(error))
            return False
        self.retry_button.set_visible(False)
        self.status.set_text(
            "Cambio transmitido por USB. Comprueba el resultado físico."
            if full
            else f"Color transmitido para {len(codes)} teclas."
        )
        if self.editor.full_known:
            pending_settings = {**self.settings, **self.editor.snapshot()}
            if self.editor.brightness > 0:
                pending_settings["resume_brightness"] = self.editor.brightness
            try:
                save(pending_settings)
                self.settings = pending_settings
            except (OSError, ValueError, StorageError) as error:
                self.status.set_text(
                    "Cambio transmitido por USB, pero no se pudo guardar: " + str(error)
                )
        if not full and len(codes) == 1 and self.verify_mode.get_active():
            self.confirm_key(next(key for key in DIAGRAM_KEYS if key["code"] in codes))
        return False

    def apply_current(self):
        # Kept as an internal full-state operation, not a manual UI button.
        if not self.editor.full_known:
            return False
        self.stop_preview()
        self.schedule_update(full=True)
        self.flush_pending()
        return True

    def apply_template(self):
        self.template_changed()

    def turn_off(self):
        if not self.editor.full_known:
            return
        self.stop_preview()
        if self.editor.brightness == 0:
            if self.pre_off is not None:
                self.editor.load(self.pre_off)
            else:
                self.editor.set_brightness(self.settings["resume_brightness"])
            self.pre_off = None
        else:
            self.pre_off = self.editor.snapshot()
            self.editor.set_brightness(0)
        self.sync_editor()
        self.schedule_update(full=True)

    def refresh_profiles(self, selected=None):
        values = list(self.settings["profiles"])
        self.names.splice(0, self.names.get_n_items(), values)
        if selected in values:
            self.dropdown.set_selected(values.index(selected))

    def selected_name(self):
        item = self.dropdown.get_selected_item()
        return item.get_string() if item else None

    def store_profiles(self, profiles, selected=None):
        save({**self.settings, "profiles": profiles})
        self.settings["profiles"] = profiles
        self.refresh_profiles(selected)

    def add_profile(self, name, profile):
        profiles = self.settings["profiles"]
        if name in profiles:
            raise ValueError("Ya existe un perfil con ese nombre.")
        self.store_profiles({**profiles, name: profile}, name)

    def profile_save(self):
        try:
            name = profile_name(self.name.get_text())
            if not self.editor.full_known:
                raise ValueError("Elige una configuración completa antes de crear un perfil.")
            self.add_profile(
                name, {**self.editor.snapshot(), "device_id": GT76_ID, "layout_id": GT76_LAYOUT}
            )
            self.profile_status.set_text("Perfil guardado: " + name)
        except (ValueError, OSError, StorageError) as error:
            self.profile_status.set_text(str(error))

    def profile_rename(self, *_):
        old = self.selected_name()
        if old is None:
            return
        try:
            name = profile_name(self.name.get_text())
            if name == old:
                return
            profiles = self.settings["profiles"]
            if name in profiles:
                raise ValueError("Ya existe un perfil con ese nombre.")
            self.store_profiles(
                {name if key == old else key: value for key, value in profiles.items()}, name
            )
            self.profile_status.set_text("Perfil renombrado: " + name)
        except (ValueError, OSError, StorageError) as error:
            self.profile_status.set_text(str(error))

    def profile_file(self, title, action, callback, filename=None):
        dialog = Gtk.FileChooserNative(
            title=title,
            transient_for=self.get_active_window(),
            action=action,
            accept_label=title,
            cancel_label="Cancelar",
        )
        filter = Gtk.FileFilter()
        filter.set_name("Perfiles JSON")
        filter.add_pattern("*.json")
        dialog.add_filter(filter)
        if filename:
            dialog.set_current_name(filename)

        def response(dialog, result):
            try:
                if result == Gtk.ResponseType.ACCEPT:
                    target = dialog.get_file()
                    path = target.get_path() if target else None
                    if not path:
                        raise ValueError("Elige un archivo local.")
                    callback(Path(path))
            except FileExistsError:
                self.profile_status.set_text("El archivo ya existe. Elige otro nombre.")
            except (OSError, ValueError, RecursionError, StorageError) as error:
                self.profile_status.set_text("No se pudo completar la operación: " + str(error))
            finally:
                dialog.destroy()

        dialog.connect("response", response)
        dialog.show()

    def profile_import(self, *_):
        def receive(path):
            name, profile = import_profile(path)
            self.add_profile(name, profile)
            self.profile_status.set_text("Perfil importado. Pulsa Cargar para aplicarlo.")

        self.profile_file("Importar", Gtk.FileChooserAction.OPEN, receive)

    def profile_export(self, *_):
        name = self.selected_name()
        if name is None:
            return
        profile = self.settings["profiles"][name]

        def write(path):
            export_profile(path, name, profile)
            self.profile_status.set_text("Perfil exportado: " + name)

        self.profile_file("Exportar", Gtk.FileChooserAction.SAVE, write, "steelseries-perfil.json")

    def profile_load(self):
        name = self.selected_name()
        if name:
            p = self.settings["profiles"][name]
            try:
                validate_target(p, active_keyboard())
            except (ValueError, RuntimeError) as error:
                self.status.set_text(str(error))
                return
            self.stop_preview()
            self.pre_off = None
            self.settings.update(binding(p))
            self.editor.load(p)
            self.sync_editor()
            self.schedule_update(full=True)

    def profile_delete(self):
        name = self.selected_name()
        if name is None:
            return
        try:
            profiles = dict(self.settings["profiles"])
            del profiles[name]
            self.store_profiles(profiles)
            self.profile_status.set_text("Perfil eliminado: " + name)
        except (OSError, StorageError) as error:
            self.profile_status.set_text(str(error))

    def toggle_auto(self, button):
        try:
            pending = {**self.settings, "autostart": button.get_active()}
            save(pending)
            self.settings = pending
            autostart(button.get_active())
        except (OSError, ValueError, StorageError) as error:
            self.status.set_text("No se ha podido configurar el inicio automático: " + str(error))


if __name__ == "__main__":
    application = App(smoke=arguments.smoke)
    result = application.run([sys.argv[0]])
    raise SystemExit(1 if application.startup_error else result)

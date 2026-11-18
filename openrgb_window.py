"""GTK controls for a selected external-server keyboard, without a fake key map."""

import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk

import remote_profiles
from openrgb_control import apply_colors, compose_colors


class OpenRGBWindow(Gtk.ApplicationWindow):
    def __init__(self, application, snapshot):
        super().__init__(
            application=application,
            title=snapshot.name + " · OpenRGB",
            default_width=850,
            default_height=640,
        )
        self.snapshot = snapshot
        self.colors = ["#" + "".join(f"{v:02x}" for v in rgb) for rgb in snapshot.colors]
        self.busy = False
        self.timer = None
        self.pending = set()
        self.full_pending = False
        self.closed = False
        self.set_hide_on_close(True)
        self.connect("close-request", self.flush_on_close)
        application.connect("shutdown", self.shutdown_sender)
        scroll = Gtk.ScrolledWindow()
        self.set_child(scroll)
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        for side in ("top", "bottom", "start", "end"):
            getattr(root, "set_margin_" + side)(22)
        scroll.set_child(root)
        title = Gtk.Label(label=snapshot.name, xalign=0)
        title.add_css_class("section")
        root.append(title)
        root.append(Gtk.Label(label=snapshot.reason, xalign=0, wrap=True))
        mode = (
            snapshot.modes[snapshot.active_mode].name
            if 0 <= snapshot.active_mode < len(snapshot.modes)
            else "desconocido"
        )
        root.append(
            Gtk.Label(
                label=f"Modo actual: {mode} · {len(snapshot.leds)} unidades de iluminación · {len(snapshot.zones)} zonas",
                xalign=0,
                wrap=True,
            )
        )
        root.append(
            Gtk.Label(
                label="Nombres y unidades comunicados por OpenRGB. Este listado no reproduce la distribución física. Clic para seleccionar · Ctrl para añadir o quitar · Mayús para seleccionar un rango.",
                xalign=0,
                wrap=True,
            )
        )
        self.editor = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        root.append(self.editor)
        row = Gtk.Box(spacing=12)
        self.editor.append(row)
        row.append(Gtk.Label(label="Color de la selección"))
        self.color = Gtk.ColorButton()
        self.color.set_use_alpha(False)
        self.color.connect("color-set", self.selection_color)
        row.append(self.color)
        row = Gtk.Box(spacing=12)
        self.editor.append(row)
        row.append(Gtk.Label(label="Intensidad RGB"))
        self.brightness = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.brightness.set_value(100)
        self.brightness.set_digits(0)
        self.brightness.set_hexpand(True)
        self.brightness.connect("value-changed", self.intensity_changed)
        row.append(self.brightness)
        self.flow = Gtk.FlowBox(
            selection_mode=Gtk.SelectionMode.MULTIPLE,
            activate_on_single_click=False,
            max_children_per_line=9,
            min_children_per_line=1,
            row_spacing=6,
            column_spacing=6,
        )
        self.editor.append(self.flow)
        self.labels = []
        for name in snapshot.leds:
            label = Gtk.Label(label=name)
            self.flow.insert(label, -1)
            self.labels.append(label)
        self.selection_status = Gtk.Label(xalign=0)
        self.editor.append(self.selection_status)
        self.flow.connect("selected-children-changed", self.selection_changed)
        row = Gtk.Box(spacing=10)
        self.editor.append(row)
        for label, action in [
            ("Seleccionar todo", self.flow.select_all),
            ("Limpiar selección", self.flow.unselect_all),
            ("Apagar", lambda: self.brightness.set_value(0)),
        ]:
            button = Gtk.Button(label=label)
            button.connect("clicked", lambda _, callback=action: callback())
            row.append(button)
        row = Gtk.Box(spacing=8)
        self.editor.append(row)
        self.profiles = Gtk.DropDown(model=Gtk.StringList.new([]))
        self.profiles.set_hexpand(True)
        row.append(self.profiles)
        for label, callback in [("Cargar", self.load_profile), ("Eliminar", self.delete_profile)]:
            button = Gtk.Button(label=label)
            button.connect("clicked", callback)
            row.append(button)
        row = Gtk.Box(spacing=8)
        self.editor.append(row)
        self.profile_name = Gtk.Entry(
            placeholder_text="Nombre del perfil para este dispositivo", hexpand=True
        )
        row.append(self.profile_name)
        button = Gtk.Button(label="Guardar perfil")
        button.connect("clicked", self.save_profile)
        row.append(button)
        self.status = Gtk.Label(
            label="Los cambios se envían automáticamente. La intensidad aplica los colores de la muestra a todo el dispositivo.",
            xalign=0,
            wrap=True,
        )
        root.append(self.status)
        root.append(
            Gtk.Label(
                label="El envío al servidor no confirma la respuesta USB ni el resultado físico. No se guardan ajustes en la memoria del teclado ni se activa restauración automática para este adaptador.",
                xalign=0,
                wrap=True,
            )
        )
        self.retry = Gtk.Button(label="Reintentar envío")
        self.retry.set_visible(False)
        self.retry.connect("clicked", lambda *_: self.send_pending())
        root.append(self.retry)
        self.editor.set_sensitive(snapshot.writable)
        self.selection_changed()
        self.repaint()
        self.refresh_profiles()

    def repaint(self):
        colors = compose_colors(self.colors, self.brightness.get_value())
        for label, rgb, name in zip(self.labels, colors, self.snapshot.leds):
            # Escape device-provided names; never treat them as markup.
            text = GLib.markup_escape_text(name)
            rgb_hex = "#" + "".join(f"{v:02x}" for v in rgb)
            label.set_markup(f'<span foreground="{rgb_hex}">●</span> {text}')

    def selected_indices(self):
        return {child.get_index() for child in self.flow.get_selected_children()}

    def selection_changed(self, *_):
        indices = self.selected_indices()
        self.color.set_sensitive(bool(indices))
        self.selection_status.set_text(f"Unidades seleccionadas: {len(indices)}")
        selected_colors = {self.colors[i] for i in indices}
        if len(selected_colors) == 1:
            rgba = Gdk.RGBA()
            rgba.parse(next(iter(selected_colors)))
            self.color.set_rgba(rgba)

    def selection_color(self, *_):
        indices = self.selected_indices()
        if not indices:
            return
        rgba = self.color.get_rgba()
        color = "#" + "".join(f"{round(v * 255):02x}" for v in (rgba.red, rgba.green, rgba.blue))
        for index in indices:
            self.colors[index] = color
        self.repaint()
        self.schedule_send(indices)

    def intensity_changed(self, *_):
        self.repaint()
        self.schedule_send()

    def schedule_send(self, indices=None):
        if not self.snapshot.writable:
            return
        if indices is None:
            self.full_pending = True
        else:
            self.pending.update(indices)
        if self.timer is not None:
            GLib.source_remove(self.timer)
        self.timer = GLib.timeout_add(180, self.send_pending)

    def send_pending(self):
        self.timer = None
        if self.busy or not (self.full_pending or self.pending):
            return False
        self.busy = True
        indices = None if self.full_pending else frozenset(self.pending)
        self.pending.clear()
        self.full_pending = False
        self.status.set_text("Enviando cambios al servidor local…")
        colors = list(self.colors)
        brightness = self.brightness.get_value()
        snapshot = self.snapshot
        application = self.get_application()
        application.hold()

        def work():
            try:
                apply_colors(snapshot, colors, brightness, indices=indices)
                success = True
                message = "Cambios enviados al servidor. Comprueba el resultado en el teclado."
            except Exception as error:
                success = False
                message = "No se pudo enviar: " + str(error)
            GLib.idle_add(finish, message, success)

        def finish(message, success):
            try:
                self.busy = False
                if self.closed:
                    return False
                self.status.set_text(message)
                self.retry.set_visible(not success)
                if not success:
                    self.full_pending = self.full_pending or indices is None
                    self.pending.update(indices or ())
                    if self.timer is not None:
                        GLib.source_remove(self.timer)
                        self.timer = None
                elif self.timer is None:
                    self.send_pending()
                return False
            finally:
                application.release()

        threading.Thread(target=work, daemon=True).start()
        return False

    def flush_on_close(self, *_):
        if self.timer is not None:
            GLib.source_remove(self.timer)
            self.timer = None
        self.send_pending()
        return False

    def shutdown_sender(self, *_):
        self.closed = True
        if self.timer is not None:
            GLib.source_remove(self.timer)
            self.timer = None

    def refresh_profiles(self):
        try:
            self.profiles.set_model(Gtk.StringList.new(remote_profiles.names(self.snapshot)))
        except Exception as error:
            self.status.set_text(str(error))

    def selected_profile(self):
        item = self.profiles.get_selected_item()
        return item.get_string() if item else None

    def save_profile(self, *_):
        try:
            remote_profiles.put(
                self.snapshot,
                self.profile_name.get_text(),
                self.colors,
                self.brightness.get_value(),
            )
            self.refresh_profiles()
            self.status.set_text("Perfil guardado para este dispositivo y mapa.")
        except Exception as error:
            self.status.set_text(str(error))

    def load_profile(self, *_):
        name = self.selected_profile()
        if not name:
            return
        try:
            self.colors, brightness = remote_profiles.get(self.snapshot, name)
            self.brightness.set_value(brightness)
            self.selection_changed()
            self.repaint()
            self.schedule_send()
        except Exception as error:
            self.status.set_text(str(error))

    def delete_profile(self, *_):
        name = self.selected_profile()
        if not name:
            return
        try:
            remote_profiles.delete(self.snapshot, name)
            self.refresh_profiles()
            self.status.set_text("Perfil eliminado.")
        except Exception as error:
            self.status.set_text(str(error))

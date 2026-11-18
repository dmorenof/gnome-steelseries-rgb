"""Read session configuration; this cannot identify printed keycaps over USB."""

import json
from pathlib import Path


def detect_layout():
    result = {"sources": [], "source": "unknown", "diagram": None}
    try:
        from gi.repository import Gio

        schema_source = Gio.SettingsSchemaSource.get_default()
        if (
            schema_source is None
            or schema_source.lookup("org.gnome.desktop.input-sources", True) is None
        ):
            return result
        settings = Gio.Settings.new("org.gnome.desktop.input-sources")
        sources = list(settings.get_value("sources").unpack())
        result.update(sources=[list(s) for s in sources], source="GNOME")
        # Multiple input sources do not establish the physical keycap layout.
        if sources == [("xkb", "es")]:
            from devices import identify_devices

            if any(device.supported for device in identify_devices()):
                result["diagram"] = "gt76-es-iso"
    except (ImportError, RuntimeError, TypeError):
        pass
    return result


def describe_layout(result):
    sources = ", ".join(code for kind, code in result["sources"]) or "no disponible"
    if result["diagram"] == "gt76-es-iso":
        return "GNOME: español (es) · GT76 español ISO · 102 teclas"
    return f"Distribución configurada: {sources} · diagrama físico sin verificar"


def save_detection(path):
    result = detect_layout()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return result

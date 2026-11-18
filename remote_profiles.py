"""Atomic, map-bound profile storage for external OpenRGB devices."""

from pathlib import Path

from color_math import rgb_value
from profile_binding import profile_name
from storage import StorageError, file_lock, read_json, write_json


def path():
    return Path.home() / ".config/titan-rgb/openrgb-profiles.json"


def load():
    data = read_json(path(), {"schema_version": 1, "devices": {}})
    if (
        not isinstance(data, dict)
        or type(data.get("schema_version")) is not int
        or data["schema_version"] != 1
        or not isinstance(data.get("devices"), dict)
    ):
        raise StorageError("Unsupported OpenRGB profile format.")
    if any(not isinstance(profiles, dict) for profiles in data["devices"].values()):
        raise StorageError("Invalid OpenRGB profile collection.")
    return data


def names(snapshot):
    return list(load()["devices"].get(snapshot.id, {}))


def validate(snapshot, profile):
    if not isinstance(profile, dict) or profile.get("layout_id") != snapshot.layout_id:
        raise ValueError("El perfil pertenece a otro mapa de iluminación.")
    colors = profile.get("colors")
    if not isinstance(colors, list) or len(colors) != len(snapshot.leds):
        raise ValueError("Número de colores incompatible.")
    brightness = profile.get("brightness")
    for color in colors:
        rgb_value(color, brightness)
    return list(colors), float(brightness)


def put(snapshot, name, colors, brightness):
    name = profile_name(name)
    profile = {"layout_id": snapshot.layout_id, "colors": list(colors), "brightness": brightness}
    validate(snapshot, profile)
    with file_lock(path()):
        data = load()
        profiles = data["devices"].setdefault(snapshot.id, {})
        if name in profiles:
            raise ValueError("Ya existe un perfil con ese nombre.")
        profiles[name] = profile
        write_json(path(), data)


def get(snapshot, name):
    return validate(snapshot, load()["devices"].get(snapshot.id, {}).get(name))


def delete(snapshot, name):
    with file_lock(path()):
        data = load()
        data["devices"].get(snapshot.id, {}).pop(name, None)
        write_json(path(), data)

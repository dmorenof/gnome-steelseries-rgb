"""Preserve legacy profiles but never silently apply a different device map."""

from color_math import rgb_value
from devices import GT76_ID, GT76_LAYOUT
from effects import TEMPLATES
from lighting import clean_key_colors

SCHEMA_VERSION = 2


def binding(data):
    return {
        "device_id": data.get("device_id", GT76_ID),
        "layout_id": data.get("layout_id", GT76_LAYOUT),
    }


def validate_target(data, device):
    identity = binding(data)
    if not device.supported or identity["device_id"] != device.id:
        raise ValueError("Este perfil pertenece a otro dispositivo. No se ha enviado al teclado.")
    if identity["layout_id"] != GT76_LAYOUT:
        raise ValueError(
            "El mapa de iluminación de este perfil no está validado para este teclado."
        )


def profile_name(value):
    if not isinstance(value, str):
        raise ValueError("El nombre del perfil debe ser texto.")
    name = value.strip()
    if not 1 <= len(name) <= 60 or not name.isprintable():
        raise ValueError("Escribe un nombre de perfil de 1 a 60 caracteres.")
    return name


def validate_profile(profile, require_binding=False):
    if not isinstance(profile, dict):
        raise ValueError("Configuración de perfil inválida.")
    identity = binding(profile)
    if (
        (require_binding and ("device_id" not in profile or "layout_id" not in profile))
        or identity["device_id"] != GT76_ID
        or identity["layout_id"] != GT76_LAYOUT
    ):
        raise ValueError("El archivo pertenece a otro teclado o mapa.")
    if "color" not in profile or "brightness" not in profile:
        raise ValueError("El perfil requiere color e intensidad.")
    color = profile["color"]
    brightness = profile["brightness"]
    if type(brightness) not in (float, int) or not 0 <= brightness <= 100:
        raise ValueError("Intensidad de perfil inválida.")
    rgb_value(color, brightness)
    effect = profile.get("effect", "solid")
    if effect != "solid" and (not isinstance(effect, str) or effect not in TEMPLATES):
        raise ValueError("Muestra de iluminación desconocida.")
    overrides = profile.get("key_colors", {})
    colors = clean_key_colors(overrides)
    if not isinstance(overrides, dict) or len(colors) != len(overrides):
        raise ValueError("El perfil contiene colores o teclas inválidos.")
    return {
        "color": color,
        "brightness": float(brightness),
        "effect": effect,
        "key_colors": colors,
        **binding(profile),
    }


def validate_portable_profile(profile):
    return validate_profile(profile, require_binding=True)


def import_profile(path):
    with path.open("rb") as stream:
        raw = stream.read(65537)
    if len(raw) > 65536:
        raise ValueError("El archivo de perfil supera los 64 KiB.")
    from storage import decode_json

    data = decode_json(raw)
    if (
        not isinstance(data, dict)
        or data.get("format") != "titan-rgb-profile"
        or type(data.get("version")) is not int
        or data["version"] != 1
    ):
        raise ValueError("Formato de perfil no compatible.")
    name = data.get("name")
    if not isinstance(name, str):
        raise ValueError("El archivo no contiene un nombre de perfil válido.")
    return profile_name(name), validate_portable_profile(data.get("profile"))


def export_profile(path, name, profile):
    data = {
        "format": "titan-rgb-profile",
        "version": 1,
        "name": profile_name(name),
        "profile": validate_portable_profile(profile),
    }
    from storage import create_bytes, encode_json

    create_bytes(path, encode_json(data))

"""Validated settings with optimistic concurrency and legacy-profile migration."""

from copy import deepcopy
from pathlib import Path

from devices import GT76_ID, GT76_LAYOUT
from profile_binding import SCHEMA_VERSION, profile_name, validate_profile
from storage import (
    StorageError,
    create_bytes,
    decode_json,
    encode_json,
    file_lock,
    read_bytes,
    write_bytes,
)

DEFAULT = {
    "color": "#64a8ff",
    "brightness": 60,
    "profiles": {},
    "autostart": False,
    "resume_brightness": 60,
    "effect": "solid",
    "key_colors": {},
    "schema_version": SCHEMA_VERSION,
    "device_id": GT76_ID,
    "layout_id": GT76_LAYOUT,
}


def normalize(data):
    if not isinstance(data, dict):
        raise ValueError("Settings must be a JSON object.")
    version = data.get("schema_version", 1)
    if type(version) is not int or not 1 <= version <= SCHEMA_VERSION:
        raise ValueError("Settings version is unsupported. Use a compatible application version.")
    result = {**deepcopy(DEFAULT), **deepcopy(data)}
    result.update(validate_profile(result))
    if type(result["autostart"]) is not bool:
        raise ValueError("Login restoration must be true or false.")
    resume = result["resume_brightness"]
    if type(resume) not in (int, float) or not 1 <= resume <= 100:
        raise ValueError("The recovery intensity must be between 1 and 100.")
    profiles = result["profiles"]
    if not isinstance(profiles, dict) or len(profiles) > 1000:
        raise ValueError("The profile collection is invalid.")
    if any(profile_name(name) != name for name in profiles):
        raise ValueError("Profile names must use their canonical form.")
    result["profiles"] = {name: validate_profile(profile) for name, profile in profiles.items()}
    result["schema_version"] = SCHEMA_VERSION
    return result


class SettingsStore:
    def __init__(self, path):
        self.path = Path(path)
        self.loaded = False
        self.revision = None

    def load(self):
        try:
            raw = read_bytes(self.path)
            data = normalize({} if raw is None else decode_json(raw))
        except (OSError, ValueError, TypeError, RecursionError, StorageError) as error:
            raise StorageError(f"Cannot read settings at {self.path}. {error}") from error
        self.revision = raw
        self.loaded = True
        return data

    def check_revision(self):
        if not self.loaded or read_bytes(self.path) != self.revision:
            raise StorageError(
                "Settings changed in another process. Reopen the application to load them."
            )

    def save(self, data):
        if not self.loaded:
            self.load()
        normalized = normalize(data)
        raw = encode_json(normalized)
        with file_lock(self.path):
            current = read_bytes(self.path)
            if current != self.revision:
                raise StorageError(
                    "Settings changed in another process. Reopen the application to load them."
                )
            if current is not None:
                version = decode_json(current).get("schema_version", 1)
                backup = self.path.with_name("settings.before-v2.json")
                if version < SCHEMA_VERSION and not backup.exists():
                    # Exclusive creation keeps the first legacy backup intact.
                    create_bytes(backup, current)
            write_bytes(self.path, raw)
            self.revision = raw

"""Persist explicit human observations, never infer them from USB success."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from devices import GT76_ID, GT76_LAYOUT
from keyboard_layout import KEYS
from storage import StorageError, file_lock, read_json, write_json
from version import APP_VERSION

RESULTS = ("correct", "different", "no-change")
CODES = {key["code"] for key in KEYS}
MAP_REVISION = hashlib.sha256(
    json.dumps(KEYS, sort_keys=True, ensure_ascii=False).encode()
).hexdigest()


def key_name(key):
    label = key["label"].replace("\n", " ")
    if 83 <= key["code"] <= 99:
        return label + " · numérico"
    if key["x"] >= 16.5 and key["y"] == 0:
        return label + " · navegación"
    if label in ("Ctrl", "Mayús"):
        return label + (" izquierdo" if key["x"] == 0 else " derecho")
    return label


class Verification:
    def __init__(self, path=None):
        self.path = Path(path) if path else Path.home() / ".config/titan-rgb/map-verification.json"

    def _load(self):
        try:
            data = read_json(self.path, {"schema_version": 1, "maps": {}})
        except (OSError, StorageError) as error:
            raise RuntimeError(
                "No se puede leer el registro de comprobaciones. No se sobrescribirá."
            ) from error
        if (
            not isinstance(data, dict)
            or type(data.get("schema_version")) is not int
            or data["schema_version"] != 1
            or not isinstance(data.get("maps"), dict)
        ):
            raise RuntimeError("Formato de comprobaciones no compatible.")
        return data

    def states(self):
        record = self._load()["maps"].get(MAP_REVISION, {})
        if not isinstance(record, dict):
            raise RuntimeError("Registro de mapa inválido.")
        states = record.get("keys", {})
        if not isinstance(states, dict):
            raise RuntimeError("Registro de teclas inválido.")
        return {
            key: value
            for key, value in states.items()
            if key in {str(code) for code in CODES}
            and isinstance(value, dict)
            and value.get("result") in RESULTS
            and value.get("source") == "user-observation"
        }

    def record(self, code, result, note=""):
        if type(code) is not int or code not in CODES or result not in RESULTS:
            raise ValueError("Comprobación de tecla no válida.")
        with file_lock(self.path):
            data = self._load()
            record = data["maps"].setdefault(
                MAP_REVISION, {"device_id": GT76_ID, "layout_id": GT76_LAYOUT, "keys": {}}
            )
            if not isinstance(record, dict) or not isinstance(record.get("keys"), dict):
                raise RuntimeError("Registro de mapa inválido.")
            record["keys"][str(code)] = {
                "result": result,
                "note": str(note).strip()[:240],
                "time": datetime.now(timezone.utc).isoformat(),
                "app_version": APP_VERSION,
                "source": "user-observation",
            }
            write_json(self.path, data)

    def report(self):
        return {
            "device_id": GT76_ID,
            "layout_id": GT76_LAYOUT,
            "map_revision": MAP_REVISION,
            "app_version": APP_VERSION,
            "total_keys": len(KEYS),
            "keys": self.states(),
            "meaning": "Resultados confirmados por una persona, no por el envío USB.",
        }

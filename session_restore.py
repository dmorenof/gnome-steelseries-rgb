"""Login restoration with bounded retries and a transport-only status report."""

import os
import time
from datetime import datetime, timezone
from pathlib import Path

import engine
from devices import active_keyboard
from lighting import apply_lighting
from profile_binding import validate_target
from storage import StorageError, read_json, write_json


def status_path():
    return (
        Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state")))
        / "titan-rgb/restore-status.json"
    )


def read_status():
    try:
        result = read_json(status_path(), {})
        return result if isinstance(result, dict) else {}
    except (OSError, StorageError):
        return {}


def _write_record(result):
    write_json(status_path(), result)


def _record(result):
    # A status-file failure must never repeat a successful hardware operation.
    try:
        _write_record(result)
    except (OSError, StorageError):
        pass


def restore(settings, attempts=5):
    if settings.get("autostart") is not True:
        return False
    if type(attempts) is not int or not 1 <= attempts <= 5:
        raise ValueError("Restoration requires between one and five attempts.")
    for index in range(attempts):
        try:
            device = active_keyboard()
            validate_target(settings, device)
            engine.stop()
            apply_lighting(
                settings["color"],
                settings["brightness"],
                settings.get("effect", "solid"),
                settings.get("key_colors", {}),
            )
            _record(
                {
                    "time": datetime.now(timezone.utc).isoformat(),
                    "result": "usb-transmitted",
                    "attempts": index + 1,
                    "visual_confirmation": False,
                }
            )
            return True
        except (RuntimeError, OSError, ValueError) as error:
            if isinstance(error, ValueError) or index == attempts - 1:
                _record(
                    {
                        "time": datetime.now(timezone.utc).isoformat(),
                        "result": "failed",
                        "attempts": index + 1,
                        "error": str(error),
                        "visual_confirmation": False,
                    }
                )
                raise
            time.sleep(2)
    return False

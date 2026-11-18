"""Desktop-entry escaping and opt-in login restoration integration."""

import sys
from pathlib import Path

from storage import write_bytes

APP_ID = "local.steelseries.rgb"
APP_NAME = "SteelSeries RGB Controller GNOME"


def desktop_value(value):
    value = str(value)
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("Control characters are not supported in installation paths.")
    return value.replace("\\", "\\\\")


def desktop_argument(value):
    # Exec quoting is decoded before general desktop-entry string escaping.
    value = str(value).replace("%", "%%")
    for char in ("\\", '"', "`", "$"):
        value = value.replace(char, "\\" + char)
    return desktop_value('"' + value + '"')


def desktop_entry(application, python=None, restore=False):
    python = sys.executable if python is None else python
    command = desktop_argument(python) + " " + desktop_argument(application / "app.py")
    if restore:
        command += " --restore"
    lines = [
        "[Desktop Entry]",
        "Type=Application",
        "Name=" + APP_NAME,
        "Exec=" + command,
        "Terminal=false",
    ]
    if restore:
        lines.append("X-GNOME-Autostart-enabled=true")
    else:
        lines.extend(
            [
                "Comment=Lighting control for supported SteelSeries keyboards",
                "Icon=" + desktop_value(application / "titan-rgb.svg"),
                "Categories=Settings;HardwareSettings;",
                "StartupNotify=true",
            ]
        )
    return "\n".join(lines) + "\n"


def set_autostart(enabled, application, home=None):
    home = Path.home() if home is None else Path(home)
    target = home / ".config/autostart/titan-rgb.desktop"
    if enabled:
        write_bytes(target, desktop_entry(Path(application), restore=True).encode())
    else:
        target.unlink(missing_ok=True)

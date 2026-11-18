#!/usr/bin/env python3
"""Install the application for one Linux user with a staged runtime replacement."""

import argparse
import ctypes.util
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from desktop_integration import APP_ID, desktop_entry, set_autostart
from distribution import DOCUMENTATION_FILES, RUNTIME_FILES
from settings import SettingsStore
from storage import file_lock, write_bytes


def check_dependencies():
    if sys.version_info < (3, 10):
        raise RuntimeError("Python 3.10 or newer is required.")
    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk

    gi.require_foreign("cairo")
    if not ctypes.util.find_library("hidapi-hidraw"):
        raise RuntimeError(
            "Install HIDAPI with the hidraw backend using your distribution package manager."
        )
    return f"Python {sys.version.split()[0]}, GTK {Gtk.get_major_version()}.{Gtk.get_minor_version()}, Cairo and HIDAPI are available."


def install(home=None, source=None):
    home = Path.home() if home is None else Path(home).absolute()
    source = Path(__file__).resolve().parent if source is None else Path(source)
    target = home / ".local/share/titan-rgb"
    if target.is_symlink():
        raise RuntimeError("The installation directory must not be a symbolic link.")
    if target.resolve() == source.resolve():
        raise RuntimeError(
            "Run the installer from the source directory, outside the installed copy."
        )
    files = RUNTIME_FILES + DOCUMENTATION_FILES
    for name in files:
        if not (source / name).is_file():
            raise FileNotFoundError(f"Missing distribution file: {name}")
    settings = SettingsStore(home / ".config/titan-rgb/settings.json").load()
    # Validate desktop paths before replacing any program files.
    entry = desktop_entry(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(target.parent / ".titan-rgb-install"):
        stage = Path(tempfile.mkdtemp(prefix=".titan-rgb-stage-", dir=target.parent))
        backup = stage.with_name(stage.name + "-previous")
        try:
            for name in files:
                destination = stage / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source / name, destination)
            # Give the retired-worker cleanup exact origins for pre-release upgrades.
            write_bytes(
                stage / "worker-origins.json",
                __import__("json")
                .dumps([str(source / "engine.py"), str(target / "engine.py")])
                .encode(),
            )
            if target.exists():
                os.replace(target, backup)
            try:
                os.replace(stage, target)
            except OSError:
                if backup.exists():
                    os.replace(backup, target)
                raise
            if backup.exists():
                shutil.rmtree(backup)
        finally:
            if stage.exists():
                shutil.rmtree(stage)
    launch = (
        "#!/bin/sh\nexec "
        + shlex.quote(sys.executable)
        + " "
        + shlex.quote(str(target / "app.py"))
        + ' "$@"\n'
    )
    for name in ("titan-rgb", "steelseries-rgb-gnome"):
        path = home / ".local/bin" / name
        write_bytes(path, launch.encode())
        path.chmod(0o755)
    applications = home / ".local/share/applications"
    write_bytes(applications / (APP_ID + ".desktop"), entry.encode())
    write_bytes(applications / "titan-rgb.desktop", (entry + "NoDisplay=true\n").encode())
    set_autostart(settings["autostart"], target, home)
    utility = shutil.which("update-desktop-database")
    if utility:
        subprocess.run([utility, str(applications)], check=False, capture_output=True)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--home",
        type=Path,
        help="Install for this home directory (also useful for staged packaging tests).",
    )
    parser.add_argument(
        "--check", action="store_true", help="Check runtime dependencies without installing."
    )
    args = parser.parse_args()
    try:
        print(check_dependencies())
        if not args.check:
            target = install(args.home)
            print(f"Installed SteelSeries RGB Controller GNOME in {target}.")
    except (ImportError, ValueError, OSError, RuntimeError) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()

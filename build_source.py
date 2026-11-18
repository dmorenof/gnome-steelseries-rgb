#!/usr/bin/env python3
"""Build a deterministic public source archive from the explicit manifest."""

import hashlib
import shutil
import zipfile
from pathlib import Path

from distribution import SOURCE_FILES
from version import APP_VERSION

FILES = SOURCE_FILES


def build(destination=None):
    root = Path(__file__).resolve().parent
    destination = Path(destination) if destination else root.parent / "titan-rgb-source.zip"
    missing = [name for name in FILES if not (root / name).is_file()]
    if missing:
        raise FileNotFoundError("Missing distribution files: " + ", ".join(missing))
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(FILES):
            entry = zipfile.ZipInfo("steelseries-rgb-gnome/" + name, (2026, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, (root / name).read_bytes())
    return destination


if __name__ == "__main__":
    source = build()
    versioned = source.with_name("steelseries-rgb-gnome-" + APP_VERSION + "-source.zip")
    shutil.copyfile(source, versioned)
    versioned.with_suffix(".zip.sha256").write_text(
        hashlib.sha256(versioned.read_bytes()).hexdigest() + "  " + versioned.name + "\n"
    )
    print(versioned)

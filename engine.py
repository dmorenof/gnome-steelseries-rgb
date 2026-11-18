"""Static previews only. Host animation streaming is disabled after hardware testing."""

import json
import os
import signal
import time
from pathlib import Path

from backend import Keyboard, rgb_value
from effects import TEMPLATES, frame

BASE = Path(__file__).resolve().parent
RUNTIME = Path(os.environ.get("XDG_RUNTIME_DIR", str(Path.home() / ".cache"))) / "titan-rgb"
PID = RUNTIME / "worker.pid"


def worker_command(command, origins):
    return len(command) >= 3 and command[1] in origins and command[2] == b"--worker"


def stop():
    # Older workers can survive a code update or lose their PID file.
    # Only terminate this user's workers from exact known application paths.
    origins = {
        str(BASE / "engine.py").encode(),
        str(Path.home() / ".local/share/titan-rgb/engine.py").encode(),
    }
    try:
        origins.update(
            path.encode()
            for path in json.loads((BASE / "worker-origins.json").read_text())
            if isinstance(path, str)
        )
    except (OSError, ValueError, TypeError):
        pass
    workers = []
    for process in Path("/proc").iterdir():
        if not process.name.isdigit():
            continue
        try:
            if process.stat().st_uid != os.getuid():
                continue
            command = (process / "cmdline").read_bytes().split(b"\0")
            if worker_command(command, origins):
                os.kill(int(process.name), signal.SIGTERM)
                workers.append(process)
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
    for _ in range(40):
        remaining = []
        for process in workers:
            try:
                if worker_command((process / "cmdline").read_bytes().split(b"\0"), origins):
                    remaining.append(process)
            except (FileNotFoundError, ProcessLookupError):
                pass
        if not remaining:
            PID.unlink(missing_ok=True)
            return
        workers = remaining
        time.sleep(0.025)
    raise RuntimeError("La animación anterior aún se está cerrando. Vuelve a intentarlo.")


def start(name, brightness):
    if name not in TEMPLATES:
        raise ValueError("Plantilla desconocida.")
    rgb_value("#000000", brightness)
    stop()
    # Validate hardware access and the first frame synchronously.
    with Keyboard() as keyboard:
        keyboard.frame(frame(name, 0, brightness))
    # Host streaming is not compatible with this controller: repeated refresh
    # commands visibly flicker, while omitting refresh leaves a frozen frame.
    # All templates are static previews until native effects are verified.
    return


if __name__ == "__main__":
    raise SystemExit("Las animaciones por software están desactivadas en este teclado.")

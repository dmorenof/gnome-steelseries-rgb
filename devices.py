"""Read-only Linux device identification. A USB ID alone never enables writes."""

from dataclasses import asdict, dataclass
from pathlib import Path

GT76_ID = "msi-klc:gt76-dt-9sf:1038:1122"
GT76_LAYOUT = "gt76-es-iso"
# Stable logical IDs are retained in saved profiles. These two physical LEDs
# occupy the Page Up / Page Down positions in this KLC protocol.
GT76_RGB_ADDRESSES = {74: 75, 77: 78}
KLC_DESCRIPTOR = bytes.fromhex(
    "06c0ff0901a10106c1ff150026ff00750809f09540810209f19540910209f2960c02b102c0"
)


@dataclass(frozen=True)
class Capabilities:
    solid: bool = False
    per_key: bool = False
    rgb_scale: bool = False
    hardware_brightness_read: bool = False
    hardware_brightness_write: bool = False
    native_effects: tuple = ()
    host_animation: bool = False
    restore_at_login: bool = False


@dataclass(frozen=True)
class Device:
    id: str
    name: str
    path: str
    backend: str
    supported: bool
    reason: str
    capabilities: Capabilities = Capabilities()

    def summary(self):
        return asdict(self)


def _read(path):
    try:
        return path.read_text().strip()
    except OSError:
        return ""


def identify_devices(sysroot=Path("/sys"), devroot=Path("/dev")):
    sysroot = Path(sysroot)
    devroot = Path(devroot)
    dmi = sysroot / "class/dmi/id"
    vendor = _read(dmi / "sys_vendor")
    product = _read(dmi / "product_name")
    board = _read(dmi / "board_name")
    # Restrict the direct backend to the exact machine family verified so far.
    gt76 = "Micro-Star" in vendor and product == "GT76 Titan DT 9SF" and board == "MS-17H1"
    devices = []
    for node in sorted((sysroot / "class/hidraw").glob("hidraw*")):
        values = dict(
            line.split("=", 1) for line in _read(node / "device/uevent").splitlines() if "=" in line
        )
        try:
            bus, vid, pid = (int(part, 16) for part in values["HID_ID"].split(":"))
        except (KeyError, ValueError):
            continue
        if vid != 0x1038:
            continue
        # Read the HID descriptor from sysfs, never a feature report.
        try:
            descriptor = (node / "device/report_descriptor").read_bytes()
        except OSError:
            descriptor = b""
        # The known GT76 control interface begins with vendor page FFC0 / usage 1.
        control = descriptor == KLC_DESCRIPTOR
        path = str(devroot / node.name)
        supported = gt76 and bus == 3 and pid == 0x1122 and control
        reason = (
            "Control estático probado en GT76 DT 9SF. Brillo interno manual."
            if supported
            else "Interfaz de entrada; sin control de iluminación habilitado."
            if pid == 0x1122 and not control
            else "Modelo o controlador sin validar; solo identificación."
        )
        devices.append(
            Device(
                GT76_ID if supported else f"hid:{vid:04x}:{pid:04x}:{node.name}",
                values.get("HID_NAME", "SteelSeries"),
                path,
                "msi-klc" if supported else "unsupported",
                supported,
                reason,
                Capabilities(True, True, True, restore_at_login=True)
                if supported
                else Capabilities(),
            )
        )
    return devices


def active_keyboard():
    candidates = [device for device in identify_devices() if device.supported]
    if len(candidates) != 1:
        raise RuntimeError(
            "No se ha identificado un único teclado compatible. No se enviaron colores a un modelo sin validar."
        )
    return candidates[0]

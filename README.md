# SteelSeries RGB Controller GNOME

An independent GTK 4 application for supported SteelSeries keyboard lighting on Linux. It provides per-key static colors, multiple-key selection, RGB intensity, personal profiles, and static lighting samples.

The direct USB backend is validated on the **MSI GT76 Titan DT 9SF**, board **MS-17H1**, with the **SteelSeries KLC 1038:1122** and a Spanish ISO 102-key diagram. Other SteelSeries keyboards can be explored through the experimental local OpenRGB adapter. Compatibility depends on the model and protocol implementation. The current UI uses Spanish labels.

This is a **pre-release**. Hardware-state readback, native animations, additional physical layouts, and second-model validation remain release gates. See [compatibility](docs/COMPATIBILITY_RESEARCH.md) and the [roadmap](docs/ROADMAP.md).

The current development checkpoint is published as **0.2.0-alpha.12** to preserve the work and allow development to continue on another computer. It is not a 1.0 release. Animation protocol findings and the next research experiments are recorded in [native effects research](docs/NATIVE_EFFECTS_STATUS.md). This independent MIT-licensed project has no official support commitment; see [support](SUPPORT.md).

## Features and evidence

| Feature | Current evidence |
| --- | --- |
| Uniform color, RGB scaling and off | Physically observed on the GT76 |
| Per-key colors and selection | User-tested GT76 editing, with automated packet and UI checks |
| Upper Home/End positions | Both changed in a joint physical check, mapped to RGB addresses 75/78 |
| Complete 102-key address map | Further individual physical checks required |
| Personal profiles, rename and JSON exchange | Storage and GTK integration checks |
| Static samples | Existing GT76 static samples, with automated composition checks |
| Animated screen preview | Local drawing only |
| Native animated keyboard effects | Research pending |
| Current hardware colors/effect/Fn brightness readback | Research pending |
| OpenRGB control | Local mock-server and GTK checks, awaiting a real second keyboard |

## Requirements

- Linux, Python **3.10 or newer**, GTK **4**, PyGObject, Cairo and HIDAPI with the **hidraw** backend.
- GNOME is the target desktop. Other Linux desktops may run GTK, but physical-layout inference currently uses GNOME input-source settings.
- A supported device and access to its lighting HID interface.

The application uses system libraries through Python and ctypes. There is no Python USB package to install. Dependency names differ between distributions. The upstream PyGObject installation guide covers distribution-specific GTK bindings. [PyGObject installation guide](https://pygobject.gnome.org/getting_started.html)

Ubuntu/Debian example

```sh
sudo apt install python3 python3-gi python3-gi-cairo gir1.2-gtk-4.0 libhidapi-hidraw0
```

Fedora example

```sh
sudo dnf install python3 python3-gobject gtk4 hidapi
```

Arch Linux example

```sh
sudo pacman -S python python-gobject python-cairo gtk4 hidapi
```

Distribution examples are dependency guidance. Current physical validation used Ubuntu on the GT76. CI definitions cover Ubuntu and Fedora software checks. Successful CI execution and hardware validation are tracked separately in [testing](docs/TESTING.md).

## Install

Extract a source archive, open its directory, and run these commands as your normal desktop user.

```sh
python3 install.py --check
python3 install.py
```

The installer stages a complete runtime before replacing an existing installation. It installs the menu entry and these user paths

- `~/.local/share/titan-rgb/` for program files and bundled licenses.
- `~/.local/bin/steelseries-rgb-gnome` and the legacy `titan-rgb` launcher.
- `~/.local/share/applications/local.steelseries.rgb.desktop` for the application menu.

The `titan-rgb` storage names preserve compatibility with earlier pre-releases. Restart an already running application after an update.

For a packaging test in an isolated directory, use `python3 install.py --home /path/to/test-home`. This changes the installation destination. The application itself continues to use the real launching user's settings directory.

### GT76 HID access

The bundled rule grants access to the KLC lighting controller for the active local session.

```sh
sudo install -m 644 data/70-titan-rgb.rules /etc/udev/rules.d/70-titan-rgb.rules
sudo udevadm control --reload-rules
```

The rule applies to a newly enumerated device. A normal reboot is the simplest way to apply it to an integrated keyboard. Once configured, launch the application as your normal user. The current GT76 setup already has this rule.

### Launch

Open **SteelSeries RGB Controller GNOME** in the application menu, or run

```sh
~/.local/bin/steelseries-rgb-gnome
```

## Editing

Opening the application loads its saved configuration into the controls and diagram. Opening and selecting keys do not send lighting commands. The diagram represents the application's configuration. Hardware readback is still under investigation.

Click a key to select it. **Ctrl** adds or removes keys, **Shift** extends a range in diagram order, and **Ctrl+Shift** adds a range. **Ctrl+A** selects all keys while the diagram has focus. **Esc** clears the selection. The color chooser, palette and a complete hexadecimal value such as `#00CCAA` apply to selected keys. Changes are grouped after a short pause. A single-key edit sends only that selection's addresses.

**Intensidad RGB** scales the colors of the entire displayed configuration. It preserves the configuration's different colors. If another program changed the keyboard since this configuration was saved, changing global intensity replaces that external state with the configuration shown. RGB scaling and the keyboard's internal Fn brightness are separate controls. On the validated GT76, **Fn + numpad minus** raises the internal brightness and **Fn + numpad plus** lowers it.

**Apagar** sets the application's RGB intensity to zero. **Recuperar iluminación** restores the configuration and a remembered positive intensity. The remembered intensity is also available after reopening the application. It cannot recover a hardware state that was never read.

If a USB operation fails, **Reintentar envío** retries the pending change. A transfer may have reached only part of the keyboard. The status distinguishes a transport failure from a settings-save failure after successful transport.

### Profiles

In **Tus perfiles**, enter a name and choose **Crear perfil**. Select an existing profile and use **Renombrar seleccionado**, **Eliminar**, **Importar…** or **Exportar seleccionado…**. A profile includes the device/map binding, base color, intensity, static sample and individual overrides. Duplicate names are rejected. Importing a profile adds it to the collection. **Cargar** applies the selected profile.

Portable JSON profile format version 1 is documented in [architecture](docs/ARCHITECTURE.md). Imports are limited to 64 KiB and require a compatible device/map. File export uses exclusive creation, so choose a new destination filename.

Settings and profiles are stored in `~/.config/titan-rgb/settings.json`. Writes are atomic. A stale instance is stopped from replacing settings changed by another process. Reopen it to load the current file. Invalid or unsupported settings display an error and are preserved for recovery. Migration of legacy schema 1 creates `settings.before-v2.json` before the first successful schema 2 save.

### Static samples and screen preview

Plain, Aqua, Chakra, Disco, Drain, Freeway, Rainbow Split and Roulette are compatible recreations. Selecting one applies a single static image to the keyboard. The animation checkbox animates the drawing. Smooth hardware effects remain under investigation after host-streamed frames caused visible flicker. [Effect research status](docs/NATIVE_EFFECTS_STATUS.md)

### Login restoration

Login restoration is opt-in through the checkbox near the bottom of the main window. It applies the saved configuration after login and can replace lighting left by Windows. It starts disabled in a new configuration. Installation follows the saved choice. Leaving restoration disabled preserves the firmware's lighting until an explicit edit.

### OpenRGB

Use **Consultar teclados en OpenRGB** to query an already running local server at `127.0.0.1:6742`. Select a SteelSeries keyboard and open its controls. The adapter requires an existing per-LED color mode and rechecks device identity, map and mode before each update. The list shows units reported by OpenRGB, which may represent individual keys or zones.

Selection and automatic editing follow the same pattern as the main window. Partial edits preserve the latest colors reported by the server for unselected units. Intensity, off and profile loading update the full displayed configuration. Edits are serialized and queued while a previous request is running. A close flushes pending changes with a bounded network timeout. Failed requests retain their edits for explicit retry.

The OpenRGB SDK reports server-side color state and has no UpdateLEDs acknowledgement in protocol version 0. Socket delivery therefore gives less evidence than an observed hardware change. OpenRGB itself may control other peripherals according to its own configuration. This application's adapter filters keyboard metadata and blocks a detected duplicate of the direct GT76 backend. [OpenRGB public protocol](https://github.com/CalcProgrammer1/OpenRGB/blob/master/NetworkProtocol.h)

## Diagnosis and development

These commands inspect metadata or exercise the GUI lifecycle

```sh
python3 app.py --version
python3 app.py --list-devices
python3 app.py --smoke
python3 -m unittest discover -v
```

`--smoke` opens an isolated application instance and closes it after approximately 1.2 seconds. It does not apply lighting. The optional Fn diagnostic reads selected Linux input events for 30 seconds and may need additional permissions. Its use is documented in [testing](docs/TESTING.md).

For formatting, CI, adversarial checks and hardware validation procedures, see [testing](docs/TESTING.md), [architecture](docs/ARCHITECTURE.md) and the [release checklist](docs/RELEASE_CHECKLIST.md) and [software review](docs/REVIEW.md).

## Remove the user installation

Close the application, then remove the program and launchers

```sh
rm -rf ~/.local/share/titan-rgb
rm -f ~/.local/bin/titan-rgb ~/.local/bin/steelseries-rgb-gnome
rm -f ~/.local/share/applications/titan-rgb.desktop
rm -f ~/.local/share/applications/local.steelseries.rgb.desktop
rm -f ~/.config/autostart/titan-rgb.desktop
```

Personal settings and profiles remain in `~/.config/titan-rgb/` until explicitly removed. The system udev rule can be removed separately if access is no longer wanted.

## License and independence

Application code is MIT licensed. The packet builder and keycode table retain the upstream MIT notice and revision. Runtime dependencies retain their respective licenses. This is an independent community project with best-effort maintenance. [License](LICENSE), [third-party provenance](THIRD_PARTY.md), [support](SUPPORT.md), [contributing](CONTRIBUTING.md)

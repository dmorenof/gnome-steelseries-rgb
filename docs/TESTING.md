# Testing

Run commands from the source directory. Automated tests use temporary settings, mock HID calls and a loopback OpenRGB test server. Test results establish code and packet behavior. Hardware evidence has its own record.

## Software checks

Install the GTK system dependencies from the README. A graphical session is unnecessary for the ordinary unit suite.

```sh
python3 -m unittest discover -v
python3 install.py --check
python3 app.py --list-devices
```

To run the GTK integration checks in the current desktop session

```sh
TITAN_RGB_UI_TESTS=1 python3 -m unittest test_ui -v
python3 app.py --smoke
```

Tests use `Gio.ApplicationFlags.NON_UNIQUE` so they do not create windows through an existing production application's remote registration. An earlier manual test violated that lifecycle and caused a Python/GTK crash. The regression fixtures isolate application instances with unique test IDs and intercept writes.

On a headless Linux test host with Xvfb and a session bus

```sh
dbus-run-session -- xvfb-run -a env GSK_RENDERER=cairo TITAN_RGB_UI_TESTS=1 python3 -m unittest test_ui -v
```

Ruff is an optional development dependency. CI pins version 0.14.5 for reproducibility.

```sh
ruff check .
ruff format --check .
python3 build_source.py
```

The vendored packet/keycode files are excluded from formatting. Retain their provenance and license when making changes.

## What the regression suite covers

- Color ranges, boolean/non-finite input rejection and static frame composition.
- Complete packet validation before writes, partial selection and Home/End translation.
- Cross-process transaction locks and stopped refresh after an incomplete report.
- Corrupt/future settings preservation, stale-writer rejection and legacy backup.
- Atomic replacement failure and concurrent OpenRGB profile updates.
- Device identity, descriptor gating, malformed/truncated SDK metadata and map/mode changes.
- TCP fragmentation, server-reported color merging and permitted command boundaries.
- Startup/selection without writes, invalid hexadecimal input, USB retry and off/recovery.
- Profile rename/export/import roundtrips and duplicate protection.
- Queued remote edits and window close while a request is in flight.
- Installation rollback, special-character paths, license inclusion and deterministic source archives.

CI definitions cover Ubuntu 22.04/24.04 and Fedora 43 with system GTK dependencies and mocked device writes. Workflow definitions are prepared locally. Their hosted results must be recorded after the repository is created. Installed-library and hardware results from this GT76 do not establish compatibility with another laptop.

## Physical GT76 procedure

Record the device, board, EC/KLC versions, application version and active layout. Preserve a personal profile before deliberately changing colors. Opening the application should preserve existing hardware lighting. The drawing should identify its saved configuration as such.

1. Select one ordinary key and apply a distinct static color. Observe whether only that physical key changes.
2. Repeat separately for Home and End, including different colors on the pair. The existing observation confirms a joint green update only.
3. Exercise Ctrl toggling, Shift ranges and Ctrl+Shift additions, including the numeric keypad. Compare the actual affected keys with the selection.
4. Create a configuration with at least three different colors. Change global RGB intensity and observe every region.
5. Save/load a named profile. Close and reopen the application, checking that the drawing restores the saved editor configuration without applying a new hardware state.
6. Turn off, reopen, and test recovery. Repeat at zero internal Fn brightness to distinguish RGB state from the internal level.
7. Record each key's result through the optional map verification controls. Export the report when useful.

A success return from HIDAPI is recorded as transport acceptance. Animation quality and key address correctness need physical observation. Checks that cannot be performed in the current session stay pending in the release checklist.

## Fn event diagnostic

`python3 diagnose_fn.py` observes selected input devices for 30 seconds. It prints only recognized lighting/numpad events and counts other signals. Input permissions may require running this diagnostic with elevated privileges. It reads events and closes descriptors on exit. Run the application itself as the normal desktop user.

No event observed outside an actual keypress interval is evidence about that keypress. Lack of an observed event also does not establish the firmware transport.

## Windows investigation

The next hardware research step requires the same GT76 running its installed Engine/GG version. Capture startup before editing, static white, changes of Fn brightness, a recovery attempt through GG without Fn, and a known working official effect. Annotate whether GG was already active in the background and whether opening it changed the lighting.

A private capture kit exists in the development workspace. It is not part of the application source package. Bring raw captures and observations back for offline analysis. Consult the [effect research status](NATIVE_EFFECTS_STATUS.md) before implementing any native effect support.


## Native-effect research tool

`python3 tools/inspect_effect.py FILE` inspects one binary effect payload offline. Add `--hex` for hexadecimal text. See the [native-effect status](NATIVE_EFFECTS_STATUS.md) for checks and interpretation limits. The regression suite includes synthetic and mutated payloads. Parser acceptance never enables hardware transmission.

# Architecture

The code follows a small set of concrete responsibilities. Device-specific protocol code, state, persistence and GTK interaction have separate modules. Shared color scaling and file operations avoid duplicate validation. Additional abstraction should follow a demonstrated second implementation.

## State and application flow

`app.py` owns the GTK application, selection events and the 180 ms edit debounce. `editor_state.py` stores the desired color configuration. `key_selection.py` describes the GT76's visual-order selection. `keyboard_layout.py` owns drawing geometry, hit testing and stable logical key identifiers. `color_math.py` validates and scales RGB colors. `lighting.py` composes static frames, and `effects.py` generates the static/screen-only recreations.

Opening the editor loads saved settings and creates a drawing. It makes no hardware write. A partial color edit collects logical codes. A global intensity, sample or profile edit requests a full configuration. The direct flush validates the device binding and serializes a transaction through `backend.Keyboard`. The loaded settings revision is checked before transmission. USB completion updates the status. Persistence is attempted afterwards and gets a separate failure message.

An explicit USB failure retains pending edits for retry. Automatic retries do not run indefinitely. The direct backend uses synchronous transactions on the UI thread. A normal full static update includes approximately 100 ms of protocol delays. A slow HID operation can temporarily delay UI response. Moving direct transactions to a worker requires preserving close/flush behavior and is a future responsiveness improvement.

## Device boundary

`devices.py` reads Linux sysfs and DMI. The supported direct target must match the MSI vendor, exact GT76 product, MS-17H1 board, USB vendor/product and the known complete control-interface descriptor. A matching USB ID alone cannot enable this backend. `backend.py` opens the resulting hidraw path through HIDAPI.

Direct transmission uses the established 524-byte static 0x0E reports and a 64-byte 0x09 refresh. Complete frames are validated before the first transfer. A failed report stops the transaction before refresh. Partial writes use the same format for selected addresses. The original packet builder remains under `vendor/` with its MIT notice.

A per-user advisory file lock in the runtime directory serializes the direct backend and this process's OpenRGB adapter. It coordinates cooperating application processes. Other lighting programs can still write independently.

### Stable logical and physical keys

Saved profiles keep logical Home/End codes 74/77. On the validated GT76, these are translated to physical RGB addresses 75/78. Both keys responded in a joint user-observed test. Full frames and partial edits use the translation. Logical identifiers remain stable across the correction, preserving profile data.

The key diagram's physical RGB address metadata participates in `MAP_REVISION`. Changing it invalidates reuse of old mapping confirmations. `map_verification.py` stores only explicit human observations, their time and the application version, under the map hash. Automated delivery cannot create a physical confirmation.

## Persistence

`storage.py` provides bounded JSON decoding, duplicate-key and non-finite-number rejection, advisory file locking and atomic replacement. Writes use a mode-0600 temporary file in the destination directory, flush and fsync it, then replace the target. A failed replacement cleans up the temporary file. Directory metadata durability across sudden power loss depends on the filesystem.

`settings.py` validates settings and legacy profiles. `SettingsStore` remembers the exact bytes loaded. Under a lock, a save compares the current file with that revision. Conflicts are reported instead of overwriting another process's changes. A malformed file, unsupported schema or invalid profile stops loading. The UI displays the failure without editable controls. The first schema-1 migration saves an exclusive original-byte backup.

`remote_profiles.py` performs locked read-modify-write operations for map-bound OpenRGB profiles. `session_restore.py` uses bounded retries for access/transport and writes a transport-only result. A status-file failure cannot repeat an already successful USB operation.

The retained `titan-rgb` paths support earlier installations. User settings, exported profiles, serials, private paths and research files are excluded from the public source archive.

### Portable GT76 profiles

A profile export uses UTF-8 JSON, with at most 64 KiB accepted on import

```json
{
  "format": "titan-rgb-profile",
  "version": 1,
  "name": "Evening",
  "profile": {
    "device_id": "msi-klc:gt76-dt-9sf:1038:1122",
    "layout_id": "gt76-es-iso",
    "color": "#204060",
    "brightness": 50,
    "effect": "solid",
    "key_colors": {"74": "#ff0000", "77": "#00ff00"}
  }
}
```

Intensity is a finite JSON number between 0 and 100. Colors are six-digit hexadecimal strings. Key identifiers are canonical decimal strings from the supported logical protocol set. Static sample names are validated. Device/map identity is required in portable files. In-memory legacy profile normalization supplies the original GT76 binding when absent.

## OpenRGB

`openrgb_discovery.py` handles bounded local TCP requests for controller count and metadata in SDK version 0. `openrgb_control.py` validates serialized devices, modes, zones, matrices, LED identifiers, matrix dimensions and color counts. Identity uses a digest of device metadata, while layout identity includes LED names, numeric values and zone matrix data. A separate mode signature detects changes to the active mode or serialized mode definition.

`apply_colors` re-resolves the identity at each write. It rejects ambiguous identity, changed layouts/modes, unsupported capabilities and a detected duplicate direct device. For partial edits, unselected values come from the immediately preceding server snapshot. The final UpdateLEDs request uses SDK command 1050. There is no acknowledgement for this command in SDK v0.

`openrgb_window.py` uses GTK's multiple selection, a debounce timer, a single in-flight worker and queued changes. It holds the application while an operation completes. Closing a window flushes pending work, and application shutdown cancels future timers. Failures expose a retry control. This is an experimental adapter pending real-server and hardware validation.

## Packaging and integration

`distribution.py` declares runtime, documentation and source manifests. `build_source.py` constructs a sorted archive with fixed entry timestamps and permissions. Repeated builds from identical files produce identical ZIP bytes.

`install.py` checks dependencies and stages a complete runtime on the destination filesystem. It restores the previous runtime if the final swap fails. Menu entries and launchers follow. `desktop_integration.py` implements desktop-entry escaping and the opt-in autostart entry. `--home` permits tests against isolated installation directories.

`engine.py` retains narrowly scoped cleanup of obsolete pre-release animation workers. Its public start helper emits one static sample. Native effects have no application transmission route.

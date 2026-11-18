# Contributing

This independent project uses best-effort community maintenance. Contributions should preserve current user profiles, legacy storage paths and the distinction between desired state, accepted transport and physical observation.

## Development

Use Python 3.10 or newer and the GTK/HIDAPI dependencies listed in the README. Follow the commands in [testing](docs/TESTING.md). Keep changes small and prefer explicit validation and direct functions over speculative abstractions. Use the shared color and storage routines when extending existing behavior. Run Ruff and applicable tests before proposing a change.

## Hardware contributions

For each model, supply the exact product/board, USB vendor/product, interface descriptor, physical layout, software versions and explicit observed results. A matching vendor/product alone cannot enable writes. Identification can be added while control remains gated.

Use the known static protocol only where verified. Native effects, firmware commands, undocumented EC writes and packets captured from other models require a separate protocol review. Include enough evidence to reproduce address mapping and transport framing before enabling an operation.

Record automated checks, transport returns and visible hardware results independently. A native effect needs an actual smoothness/flicker observation on the target model. Test the integration's normal UI and command entry points, including shutdown and failure paths.

## Data and provenance

Use temporary files and mocked device writes in automated tests. Avoid committing settings, hardware serials, raw input captures or personal profiles. Exported reports should describe the observation needed for the issue.

Preserve the MIT notices and upstream revision under `vendor/`. Contributed code needs a compatible license and clear origin. Proprietary binaries, keys, decrypted descriptors and captures belong outside the public source tree. [Third-party provenance](THIRD_PARTY.md)

## Publication

Use the [release checklist](docs/RELEASE_CHECKLIST.md) to review the public archive and hardware scope. A pre-release can document incomplete capabilities. The 1.0.0 tag requires the remaining release gates and the owner's explicit publication decision.

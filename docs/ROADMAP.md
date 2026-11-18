# Roadmap

## Completed software blocks

- Exact GT76 model/control-interface identification and static USB transactions.
- Multiple-key selection, per-key color, HEX input and grouped immediate edits.
- Saved editor configuration loaded automatically, with no startup color write.
- Separate RGB intensity and off/recovery, including remembered positive intensity across reopening.
- Home/End address correction preserving existing logical profile identifiers.
- Profile creation, rename, deletion and bounded JSON import/export.
- Validated settings, corrupt-data preservation, atomic writes and stale-writer detection.
- Map verification records tied to the map revision and explicit human observations.
- Opt-in bounded login restoration and separate transport status.
- Experimental OpenRGB selection, partial edits, mode/map checks, serialized writes and retry.
- Staged installation, dependency checks, public file manifests and deterministic archives.
- Automated unit/integration checks, CI definitions and English project documentation.

## Remaining hardware blocks

1. Complete the 102-key physical address report, with separate Home/End observations and modifier-selection checks.
2. Complete the documented physical profile/intensity/off/reopen regression on the GT76.
3. Continue exact-model GG compiler/driver analysis and resolve direct-stream setup, frame headers and exit behavior. A same-machine Windows capture can corroborate startup, brightness recovery and a working effect.
4. Establish actual color/effect/internal-brightness readback, if the firmware exposes it.
5. Implement physical animation only after target-specific protocol validation: investigate both native effects and the distinct direct-color stream, with separate physical acceptance for each.
6. Validate an actual second SteelSeries device through a real OpenRGB server.

## Product extensions

- Additional physical keyboard diagrams and explicit layout selection.
- OpenRGB profile exchange between appropriately identified devices.
- A worker-based direct HID sender if synchronous USB response time becomes a usability issue.
- Broader Linux distribution and accessibility testing, plus UI localization beyond the current Spanish interface.

## Publication status

On 2026-11-18 the owner authorized publishing the current development checkpoint before shutting down the development computer, superseding the earlier completion condition for repository upload. It is a pre-release with the compatibility limitations above. The 1.0.0 tag remains reserved for a completed release. Hardware readback, smooth native effects and multi-model physical validation remain open gates. [Release checklist](RELEASE_CHECKLIST.md)


## User priority — 2026-11-17

The next feature block is physical animation support and animated templates. Start with **Rainbow Wave →**, matching the user's described GG default, then the compatible animated template set in the effect research document. Static samples and the screen preview do not satisfy that request. Native timing/geometry validation on this GT76 remains necessary. [Animation requirements and research](NATIVE_EFFECTS_STATUS.md)


The authorized publication destination is [dmorenof/gnome-steelseries-rgb](https://github.com/dmorenof/gnome-steelseries-rgb). Native-effect inspection has a bounded offline tool and malformed-frame regressions. Exact-model compiler and driver observations, including the distinct direct-color route, are documented for continuation. Physical animation remains pending same-target protocol evidence.

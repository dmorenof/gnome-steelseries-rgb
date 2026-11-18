# Native effects and animation research

## Current behavior

Static samples are transmitted as a single established static configuration. The GTK screen preview uses a local drawing timer. Its varying frames never enter the USB path. Plain remains static. The preview state is outside saved profiles and login restoration.

Host-generated repeated 0x0E frames with 0x09 refresh caused visible block flicker, especially on the numeric keypad, in user tests. Omitting refresh left lighting fixed. That transmission loop was removed.

## Native protocol gate

Upstream reports a critical controller failure after a native effect with missing transitions. A duration or transition count that appears valid is insufficient to establish complete framing or model compatibility. [Upstream issue 24](https://github.com/Askannz/msi-perkeyrgb/issues/24)

Public community effect notes and privately inspected Windows descriptors describe timing sections and key associations. The application contains no native effect constructor or transmission route. Existing static samples are independent recreations, with provenance recorded separately. [Third-party provenance](../THIRD_PARTY.md)

## Required evidence

Use an actual working effect on the same GT76 and record the KLC firmware, Engine/GG version, complete transfer framing, timing values, key associations and any refresh operation. Capture the initial application of the effect. Verify that motion continues without host frame streaming and inspect physical smoothness across all regions.

Start by analyzing captures offline. A replay implementation requires a separate model-specific review. Captured packets from another laptop or shared USB IDs do not establish compatibility. Brightness readback and internal Fn control are separate open investigations.

## Requested animation block — 2026-11-17

The user identified their GG default as a rainbow moving horizontally to the right. This is the first target for physical native-effect support. The descriptive working name is **Rainbow Wave →**. Its status is pending hardware implementation. It must remain distinct from the existing static Rainbow Split sample. Offering this effect must preserve the user's explicit startup-restoration preference.

| Target | Intended motion |
| --- | --- |
| Rainbow Wave → | Continuous rainbow bands travelling left to right across the full keyboard |
| Aqua | Smooth blue/turquoise travelling wave |
| Chakra | Continuous whole-keyboard color cycle |
| Disco | Changing multicolor key mosaic |
| Drain | Motion toward the keyboard center |
| Freeway | Moving bands with varying color and intensity |
| Rainbow Split | Rainbow motion outward from the center |
| Roulette | A travelling colored band |

These are intended compatible recreations. The table defines requested behavior, not implemented or physically verified effects. Plain remains a static sample.

The complete block needs effect selection, speed, direction where applicable, independent RGB intensity, profile roundtrip support and full-keyboard coverage including the keypad. Acceptance requires visible smooth motion, consistent direction, reliable switching back to static lighting and repeated activation without accumulating incorrect colors. Host-generated static-frame streaming remains retired after observed flicker.

### Additional public evidence reviewed

A recent GE76 research repository reports different timing and direction semantics from the older effect notes. Its measured 10 ms ticks and direction observations apply to an ALC lightbar. Its separate KLC keyboard document explicitly leaves timing, regions and wave geometry open. This is useful comparative evidence, with a different keyboard controller and machine. It does not verify a GT76 native program. [Effect-document corrections](https://github.com/StevenHrovat/msi-laptop-ec-protocols/blob/main/docs/effectdoc-corrections.md), [keyboard-specific open questions](https://github.com/StevenHrovat/msi-laptop-ec-protocols/blob/main/docs/keyboard.md)

The downloaded upstream preset index contains other MSI model families rather than a GT76-specific capture. No same-machine Windows capture was found in the development workspace during this review. A capture remains useful corroboration, but it is not the only research route: the exact-model Windows definitions and its driver bridge are now being analyzed offline as described below.

## Exact-model reverse engineering — 2026-11-17

Private analysis of the official GG 123.0.0 installer established an inheritance chain from the GT76 definition through the GE63 definition to the KLC base and shared effect compiler. This is stronger model-specific evidence than matching a USB identifier. It still does not establish the installed firmware's behavior.

The proprietary inputs, decoded definitions, evaluator and generated outputs remain outside the public source distribution. This section records observations rather than copying vendor implementation. No Windows executable or driver was run and no new USB command was transmitted during these experiments.

| Observation | Evidence and limit |
| --- | --- |
| Effect compilation is accessible offline | A restricted Python evaluator executed the relevant pure GoLisp definitions. It exposes no file, process, network or HID primitives to those definitions. This is a research subset interpreter, not the official GG runtime. |
| Color-shift and breathing structures agree with the offline inspector | 192 synthetic six-color cases covered two effect types, three direction axes, both inversion values, first positions 0/5 and eight speed values including boundaries. All produced 151-byte bodies and structurally consistent padded effect payloads. Inputs at boundaries are arithmetic probes, not approved UI settings. |
| Rate integration is not an acceptance criterion | 54 of those structurally valid results generated drift or clipping warnings under the inspector's signed-rate hypothesis. Quantization and firmware reset behavior need investigation. A warning does not establish broken hardware output, and structural success does not establish safety. |
| There is a separate direct-color route | The inherited GT76 interface declares command `0x0C` with a count and four-byte key/R/G/B records. Its path is different from repeatedly reprogramming `0x0E` static state and refreshing with `0x09`. It may provide a useful alternative, but smoothness is untested. |
| Direct frames require an initialization lifecycle | The vendor integration first configures selected keys in host-stream mode (settings mask 2), then resets the lighting mode before direct writes. Returning to ordinary static state must also be verified. Sending only a direct-color frame omits part of this lifecycle. |
| The Windows bridge forwards feature data | Static disassembly of `ssps2.sys` shows virtual report `0x0C` selecting a feature-forwarding helper. The helper copies 525 bytes and formats IOCTL `0x000B0191`. Wrapper/report-ID sizing still needs reconciliation before constructing a Linux transaction. |
| GT76-specific historical settings exist | A GT76 migration contains historical effect settings, including six-color transitions. It is not a capture of this user's current GG default and is not a validated replay preset. |
| Shared reverse transforms exist | The shared effect definitions include transforms for onboard-profile readback. Their presence in shared code does not prove a working GT76 read API; the inspected KLC effect APIs are writes. |

Arithmetic follows integer division truncated toward zero for the exercised integer-only compiler path. The language reference also documents float32 coercion; the evaluator is not used to claim equivalence for arbitrary floating-point programs. [SteelSeries GoLisp reference](https://techblog.steelseries.com/golisp/language-ref.html)

The bridge's indirect WDF calls were identified against Microsoft's published function-table indices, including memory-buffer retrieval, request formatting and sending. Static call tracing does not establish a successful USB exchange. [Microsoft WDF function table](https://github.com/microsoft/Windows-Driver-Frameworks/blob/main/src/publicinc/wdf/kmdf/1.27/wdffuncenum.h)

### Next protocol experiments

1. Resolve virtual report headers, physical report-ID handling and exact lengths throughout the bridge. Keep compiler bodies, virtual wrappers and physical payloads distinct.
2. Reconstruct the complete direct-mode setup/frame/exit sequence offline, including grouping and physical key addresses. Review it against the existing static path before any bounded hardware test.
3. Establish native effect timing, association and restart behavior for this KLC firmware. Review every generated transition, including padding and disabled slots; never replay a complete unreviewed preset.
4. After a reviewed, recoverable single-state test, evaluate repeated direct frames separately from native effects. Neither route is enabled in the application today. Physical observations must cover all regions, repeated activation and return to static lighting.

A Windows capture on this machine can resolve uncertainties in parallel with this work. It is no longer treated as a prerequisite for all further reverse engineering.


## Offline frame inspection

The source package includes a development tool for a single captured native-effect payload. It reads files and prints JSON. It has no HID, network or replay dependency.

```sh
python3 tools/inspect_effect.py captured-effect.bin
python3 tools/inspect_effect.py captured-effect.hex --hex
python3 tools/inspect_effect.py captured-effect.hex --hex --tick-ms 10
```

The optional tick duration is an explicit timing hypothesis. Without it the report retains raw duration units. The parser checks frame length, opcode, transition count, duration sums, zero durations, indices, reserved fields and the reviewed wave/register layout. It reports color drift and clipping under the signed-rate hypothesis. KLC timing, capacity and geometry remain unverified regardless of arithmetic consistency. Every report keeps `hardware_verified` and `transmission_available` false.

Adversarial tests include 2,500 deterministic mutated/truncated frames. The supplied synthetic test frame is an arithmetic fixture, with no hardware validation. A review of both downloaded upstream model preset collections found 118 effect frames, of which 50 have zero transition count and zero total duration. Those collections target other model families. Whole-preset replay is unsuitable for target validation.

# Software review — 2026-11-17

Scope is the source tree for 0.2.0-alpha.11, its existing callers, user data, installer and public documentation. The review used adversarial cases, corrections, regression tests, a second code pass and a separate documentation pass. Development testing used Python 3.14.4 and GTK 4.22 on the available Ubuntu desktop.

## First pass and corrections

| Finding | Correction | Verification |
| --- | --- | --- |
| Invalid settings could fall back to defaults and later overwrite profiles | Validated load with an error view and preserved original bytes | Corrupt/future/duplicate-key settings regressions and GTK startup failure check |
| Two instances could replace each other's settings | Loaded-byte revision checks before transmission and before atomic save | Independent stores and a stale-GTK-writer regression |
| Remote profile read-modify-write could lose concurrent changes | Locked complete updates | Concurrent threaded profile creation |
| Some JSON values bypassed complete validation | Strict object/version/color/intensity/key checks, bounded reads and duplicate/non-finite rejection | Malformed settings and portable-profile cases |
| Aliased sparse RGB addresses could silently collide | Reject duplicate physical destinations before sending | Sparse-packet regression |
| Device gating accepted partial descriptor matches | Require the observed full control descriptor | Device fixture and unsupported-device checks |
| Failed transfers lost their pending selection | Retain pending edits and provide explicit retry | GTK failure/retry test |
| A settings error after transport could be described as a USB failure | Separate persistence and transport handling | Reviewed error path and storage failure tests |
| OpenRGB map identity omitted numeric LED addresses and matrices | Extend layout identity and mode signatures | Changed-address and changed-mode mock-server tests |
| Window close could abandon queued remote edits | Flush on close, serialize requests and hold the application during work | GTK queued-write/close test |
| Reopening an off configuration could leave recovery at zero | Persist a positive recovery intensity | Off/reopen/recover GTK test |
| Installation could copy only part of a runtime | Stage all manifest files and restore the previous runtime on swap failure | Installation rollback regression |

## Code-quality pass

The review moved shared RGB validation out of the USB adapter and moved settings, bounded atomic persistence, desktop-entry integration and distribution manifests into dedicated modules. Existing import entry points were retained where callers relied on them. The GTK UI retains direct event handlers and procedural widget construction. No generic device framework was added for unimplemented models.

Owned Python files now use a consistent formatter and lint configuration. Vendored protocol/keycode files retain their upstream form and MIT provenance. The application uses the existing static packet format and conservative device boundaries.

## Second pass

The second pass checked the changes themselves and found additional lifecycle and metadata cases. Test applications now use unique IDs as well as NON_UNIQUE flags, preventing D-Bus object reuse within a test process. Re-discovery keys include OpenRGB mode signatures. CLI flags are parsed only in the executable entry point. Generic JSON helpers are used for mapping and restoration records. Desktop escaping is exercised by launching a temporary harmless script from a path containing spaces, percent, dollar, quotes, backslash and backtick characters.

The direct HID path remains synchronous. Protocol delays account for roughly 100 ms in an ordinary complete update, and a slow HID operation can stall UI response temporarily. The settings preflight and commit checks bound stale-state mistakes but do not make filesystem persistence and hardware writes a single atomic operation. A physical device cannot be rolled back automatically after a partial USB failure.

## Documentation pass

Public Markdown documents were rewritten in English and checked against implementation entry points. The README covers dependencies, installation, editing, profiles, brightness distinctions, OpenRGB, diagnostics and removal. Architecture, testing, security/provenance, compatibility and publication gates have separate documents. Relative links are checked against the source distribution manifest. The source archive includes the licenses and uses deterministic metadata.

## Remaining evidence boundaries

- Software checks do not establish a complete physical key map or animation quality.
- Hardware-state readback and native effects still require same-machine protocol evidence.
- OpenRGB remains experimental until validated with a real second device and server.
- The direct diagram is the Spanish GT76 layout and uses GNOME input-source inference.
- Hosted CI needs a repository to run, and a second distribution needs actual desktop testing.
- Public source preparation is a pre-release outcome. The owner's 1.0.0 scope and publication decision remain separate release gates.

Final check results are recorded in the [release checklist](RELEASE_CHECKLIST.md). The [roadmap](ROADMAP.md) retains the required physical and product work.

## Final local result

The final suite passed 73 tests with the eight GTK tests enabled. Repeating the suite from the extracted public archive also passed. Ruff checks, dependency checks, staged-install tests and the installed version/smoke checks passed. Personal settings remained byte-identical across installation and smoke verification. Hosted CI and the physical gates retain their pending status in the release checklist.


## Alpha.12 native research continuation

An offline-only frame inspector was added and tested with six targeted tests plus deterministic mutation cases. A second pass corrected an overbroad slot-capacity assumption so an ALC-specific range is recorded as a compatibility note instead of a claimed KLC limit. The complete local suite now passes 79 tests. The tool reports structural issues and rate-model hypotheses, and exposes no transmission path. Native GT76 animation remains blocked on target-specific evidence, independently of parser test success.

## Exact-model reverse-engineering continuation

Private offline experiments exercised the relevant GG compiler definitions on 192 synthetic cases through a restricted research evaluator. All outputs passed the existing structural inspector; 54 retained signed-rate-model warnings. This is agreement between offline representations, not independent firmware validation. The evaluator is a language subset, not an official GG execution environment. Boundary inputs do not become supported product settings merely by compiling.

Driver tracing and the inherited GT76 definitions identified a distinct direct-color route and a host-stream initialization lifecycle. An adversarial pass found unresolved report-ID/length handling between the virtual Windows device and physical feature buffer. It also identified the need to verify exit from direct mode before an animation sender is added. No new USB commands, startup writes, or runtime animation paths were introduced. Proprietary research material remains outside the public manifests. Details and next experiments are recorded in [native effects research](NATIVE_EFFECTS_STATUS.md).

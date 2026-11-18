# Release checklist

A checked software item describes local verification of that item. Hosted CI and physical tests have separate gates.

## Software pre-release review

- [x] Unit and opt-in GTK integration suites pass after the final edits.
- [x] Ruff lint and format checks pass.
- [x] Installation/update/rollback and special-character path tests pass.
- [x] Installed version and smoke checks pass with preserved user settings.
- [x] Deterministic source archive passes manifest/license/content checks.
- [x] Extracted source archive runs the full test suite.
- [x] Public Markdown links and documented commands match the distribution.
- [x] English documentation describes actual behavior and validation limits.
- [x] The release summary identifies unresolved hardware scope.

## After creating the GitHub repository

- [ ] Confirm hosted Ubuntu and Fedora CI results.
- [ ] Review repository contents and history for user data and proprietary research.
- [ ] Enable the intended private security-reporting channel.
- [ ] Review the owner-selected pre-release scope before publishing any release.

## 1.0.0 hardware/product gates

- [ ] Complete the GT76 individual physical map report.
- [ ] Complete physical color/intensity/profile/off/reopen checks.
- [ ] Resolve hardware-state readback feasibility with same-machine Windows evidence.
- [ ] Validate a smooth, safe native animation implementation if included in 1.0 scope.
- [ ] Validate at least one additional target model or explicitly revise the intended model scope.
- [ ] Validate a second Linux distribution as an actual desktop installation.
- [x] Record the owner's conditional authorization to upload the completed project to the designated repository.

The owner previously chose to create the repository and the 1.0.0 tag when the project is finished. This review prepares a public pre-release source tree. It cannot substitute software simulations for those physical gates.

## Local result — 2026-11-17

All 73 automated tests passed with GTK integration enabled, including eight GTK tests with mocked hardware writes. The source archive was extracted and passed the same 73 tests, dependency checks and an isolated installation. Ruff lint and formatting checks passed. The installed alpha.11 runtime passed version and smoke checks, with the user's settings byte-identical and login restoration disabled. Relative Markdown links resolve within the public manifest. Vendored files retain their original contents and notices.

The workflow definitions have not yet run on hosted GitHub infrastructure. Actual Windows readback/effect captures, a complete physical map, second-device and second-distribution desktop tests remain the explicit gates above.


## Conditional publication destination — 2026-11-17

The owner authorized uploading the completed and documented project to [dmorenof/gnome-steelseries-rgb](https://github.com/dmorenof/gnome-steelseries-rgb). Repository metadata was inspected through the owner's GitHub connection. It is currently an empty public repository with push permission. Upload is conditional on completion, including the outstanding physical animations. This authorization does not mark the unresolved feature gates as passed.


## Native research continuation — 2026-11-17

Alpha.12 adds the offline inspector and six native-frame tests, including 2,500 mutated/truncated inputs. All 79 tests pass with GTK integration enabled. Fifty empty native frames were found across the two downloaded other-model preset collections and rejected. These tests do not validate a GT76 native animation. No GT76 Windows capture is present in the workspace, and no Windows volume is mounted in the current session. The condition for uploading a complete implementation remains unmet.

## Checkpoint publication authorization — 2026-11-18

The owner explicitly requested publication of the current work before shutting down the development computer. This supersedes the earlier condition that repository upload wait for completed functionality. The published scope is alpha.12 source, tests, MIT licensing, credits, English documentation and non-proprietary research observations. Personal settings, profiles, proprietary vendor inputs and decoded research artifacts are excluded. The 1.0.0 tag and outstanding physical gates remain unchanged.

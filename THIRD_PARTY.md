# Third-party components and provenance

| Component | Use and distribution |
| --- | --- |
| Askannz/msi-perkeyrgb | Static packet builder and keycode tables in `vendor/`. MIT notice and upstream revision are bundled. |
| GTK 4, PyGObject, Cairo, HIDAPI | System runtime dependencies. Their binaries are installed through the distribution and retain their own licenses. |
| OpenRGB | Optional external server. The small SDK client is implemented locally from public protocol documentation. OpenRGB binaries and controller implementations are outside this distribution. |
| Ruff | Optional development tool, version-pinned in CI. It is outside the runtime and source archive. |
| SteelSeries Engine/GG | Privately inspected during protocol research. It is outside the runtime dependencies and source distribution. |

The application is MIT licensed. The original vendored notice is preserved at `vendor/LICENSE`, with revision `e185a29e864bdda952b336940b047b5f97419d46` recorded in `vendor/UPSTREAM_COMMIT`. [Upstream repository](https://github.com/Askannz/msi-perkeyrgb)

The packet framing remains the established upstream static implementation. GT76 diagram geometry and labels were implemented from Spanish-keyboard photographs and approximate proportions. Logical-to-RGB navigation corrections use the observed response of this GT76 and retain existing profile identifiers. [GT76 photographic reference](https://www.geeknetic.es/Review/1653/Review-MSI-GT76-TITAN-DT-9SF.html)

The OpenRGB client uses public count/data serialization and UpdateLEDs. `openrgb-python` was evaluated during research and is neither imported nor redistributed. [Public protocol](https://github.com/CalcProgrammer1/OpenRGB/blob/master/NetworkProtocol.h), [controller serialization](https://github.com/CalcProgrammer1/OpenRGB/blob/master/RGBController/RGBController.cpp)

Static analysis of proprietary Windows software did occur. The project does not claim a clean-room development process. Proprietary binaries, extracted descriptors, encryption material and private captures remain outside the source tree and its explicit distribution manifest. Native effects remain a research gate with no application implementation. Future contributions derived from research require a provenance review before inclusion.


The offline effect inspector refers to TauAkiou's public effect-layout notes and the GE76 research's corrections to timing/color interpretation. It is an original parser and arithmetic checker. The reported ALC measurements are kept distinct from unverified GT76 KLC behavior. [Public corrections](https://github.com/StevenHrovat/msi-laptop-ec-protocols/blob/main/docs/effectdoc-corrections.md)

# Compatibility and evidence

## Supported direct device

| Attribute | Validated target |
| --- | --- |
| Laptop | MSI GT76 Titan DT 9SF |
| Board | MS-17H1 |
| EC observed | 17H1EMS1.103 |
| Lighting controller | SteelSeries KLC, USB 1038:1122 |
| Physical diagram | Spanish ISO, 102 keys |
| Desktop evidence | Ubuntu, GNOME, Wayland |

The direct backend also matches the full vendor-control HID descriptor. The input interface is a separate collection. A second ALC controller, 1038:1130, exists on the observed machine and has no implementation here.

Uniform/static lighting, RGB scaling and per-key editing have user observations. Home/End jointly changed to green using RGB addresses 75/78. Full individual-key mapping and modifier-selection validation remain in the physical test plan. Approximate drawing proportions are based on the photographed Spanish GT76. [Photographic reference](https://www.geeknetic.es/Review/1653/Review-MSI-GT76-TITAN-DT-9SF.html)

## Layout identification

The application reads GNOME input-source configuration. A single Spanish `es` source combined with the supported model enables the Spanish diagram. This is an inference, not a USB read of printed keycaps. Multiple sources and other physical layouts require further selection/mapping work. Detection is repeated at program startup. Installation itself does not need to identify physical keys.

## External adapter

The experimental OpenRGB adapter accepts keyboard metadata identifying SteelSeries and an active per-LED mode. It blocks a detected duplicate of the direct GT76. The metadata and controller state originate from the server. Additional physical keyboards and zone types require observation with a real server before being listed as confirmed.

## Readback research

Generic feature and input GET_REPORT operations returned zero blocks while the GT76 was visibly turquoise, including after the user lowered Fn brightness. Prefilling receive buffers with a nonzero byte confirmed that zeros replaced the buffer contents. These operations did not reveal the visible color or brightness change.

A documented output query with opcode 0x10 returned `1e 02` followed by zeros. The inspected vendor descriptor interpreted the values as minor 30 and major 2, consistent with USB `bcdDevice` 0230. Another implementation labels this query as layout identification. That layout interpretation remains unverified on this GT76 and is not used here.

The inspected msi-ec configuration recognizes the exact EC firmware but marks keyboard-backlight registers unsupported. Reviewed MSI RGB support in Linux's hid-steelseries driver targeted another model. These findings do not supply a GT76 brightness getter. A driver fork needs an identified and validated hardware operation. [msi-ec source](https://github.com/BeardOverflow/msi-ec/blob/main/msi-ec.c), [Linux SteelSeries driver](https://github.com/torvalds/linux/blob/master/drivers/hid/hid-steelseries.c)

Readback feasibility remains open. A Windows capture on the same hardware must distinguish queries, stored application configuration and automatic profile restoration. Research artifacts stay outside this distribution. [Research plan](TESTING.md)

## Distribution scope

The implementation depends on Linux hidraw, GTK, PyGObject and Cairo rather than a Debian-specific device API. Package names and desktop integration differ across distributions. Ubuntu is the observed physical environment. Ubuntu/Fedora CI definitions exercise software boundaries and installation staging. Another distribution's hardware behavior is a separate validation item.

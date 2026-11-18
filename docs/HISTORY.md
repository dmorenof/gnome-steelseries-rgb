# Development history

The project began as Titan RGB for one MSI GT76 and was renamed SteelSeries RGB Controller GNOME to reflect a broader product goal. Internal data paths retained `titan-rgb` to preserve user configuration.

Early static color tests exposed interference from an obsolete animation worker. Cleanup was restricted to exact known application script paths. Host-streamed animations then produced visible flicker, and that feature was retired. Static recreated samples and a screen-only animated preview remained available.

A low internal hardware brightness level made accepted RGB writes appear ineffective. The user recovered light using Fn plus numpad minus and confirmed it raises brightness on this GT76. The application treats this level separately from RGB intensity.

Opt-in login restoration successfully applied Aqua after login. It also replaced lighting left by Windows. The user chose to disable restoration to preserve the keyboard state at startup. Opening the UI subsequently loaded saved editor controls without writing hardware colors.

Per-key editing and modifier selection were added incrementally. Two upper navigation positions stayed white while their diagram keys were green. Sending green to physical RGB addresses 75/78 changed both. The backend now translates stable logical identifiers 74/77 to those addresses.

Generic readback returned zeros despite visible turquoise lighting. A specific 0x10 query returned bytes consistent with firmware 2.30. Readback and native-effect research remained open pending a same-machine Windows capture.

The later software review focused on data-loss boundaries, multi-process writes, transport validation, GTK lifecycle, staged installation and English documentation. The changelog records software versions. [Changelog](../CHANGELOG.md)

# Security and device-safety reporting

This is a pre-release community project with best-effort maintenance. There is no guaranteed response or security support window.

Report reproducible data-loss, command-injection, device-identification or unauthorized-write issues through a private repository security report when that facility is enabled after publication. If a private channel is unavailable, open an issue requesting a private contact without including secrets, personal captures or exploit details.

## Boundaries

- The direct backend is gated to the verified GT76 model and complete control-interface descriptor.
- USB transport and this application's OpenRGB writes use a common per-user lock.
- The SDK endpoint is fixed to IPv4 loopback. The server is a local trust boundary and supplies its own metadata/state.
- JSON reads have size limits. Settings use validation, atomic replacement and stale-writer checks.
- The application operates with session device permissions and should run as the desktop user.

Undocumented commands can harm a lighting controller. Keep any new effects or controller support behind a review with target-specific evidence. Device safety and conventional software security both belong in that review.

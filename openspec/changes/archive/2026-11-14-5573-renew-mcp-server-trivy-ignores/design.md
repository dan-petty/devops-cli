# Design

## Decisions

- **Bump where a fix exists, renew where none exists.** SECURITY.md "A Finding with No Fix" asks for a bump of the pin on the day that a fix is released, and for a renewal of 3 days otherwise, up to 14 days in all. Helm 4.3.2 holds the fix of CVE-2026-111943, so its entry goes. No kubectl release holds the fix of CVE-2026-56851 or CVE-2026-78669, so their entries get a new date.
- **The cap.** The entries first appeared on 2026-11-08 with `exp:2026-11-11`. The renewal of #4336 set 2026-11-14. This renewal sets 2026-11-17. The last renewal in the cap ends on 2026-11-22. After that date, the owner decides.
- **A tracking issue that stays open.** The old entries named #4336, which is closed. The renewed entries name #5582, which stays open until a kubectl release holds both fixes.
- **The devcontainer pin moves with the lock.** `tests/invariants/test_devcontainer_config.py` fails when `.devcontainer/Dockerfile` and `tools.lock` pin a different helm.
- **No minimum release age.** Helm 4.3.2 is one day old. The owner takes a security release at once (CONTRIBUTING.md, "Dependency Versions").

## Rejected alternatives

- **Renew all three entries.** Rejected: helm 4.3.2 is a released fix of CVE-2026-111943, and SECURITY.md forbids an ignore of a finding that has a fix.
- **Bump kubectl to 1.38.0-beta.0.** Rejected: it is a pre-release, and the project pins stable releases.
- **Build kubectl from source with newer x/net and x/text.** Rejected: a custom build is a tool to build and keep (AGENTS.md rule 3), and the renewal stays in the cap.
- **Remove kubectl and helm from the image.** Rejected: the `mcp-server` image installs them on purpose (#3220).

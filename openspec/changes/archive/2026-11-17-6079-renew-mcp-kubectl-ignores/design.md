# Design

## Decisions

- **Renew, because no release holds a fix.** SECURITY.md "A Finding with No Fix" asks for a bump of the pin on the day that a fix is released, and for a renewal of 3 days otherwise, up to 14 days in all. No stable kubectl release holds x/text 0.41.0 or x/net 0.60.0 or later, so each of the three entries gets a new date.
- **The cap.** The entries first appeared on 2026-11-08 with `exp:2026-11-11`. Renewals set 2026-11-14 (#4336), 2026-11-17 (#5573) and now 2026-11-20. A renewal on 2026-11-20 can go to 2026-11-22 only. After that date, the owner decides.
- **A tracking issue that stays open.** #5582 tracked the kubectl bump and is closed, and this pull request closes #6079. The entries name #6084, which stays open until a stable kubectl release holds the fixes.

## Rejected alternatives

- **Bump kubectl to 1.38.0-beta.0.** Rejected: it is a pre-release (`prerelease: true` in the release list of kubernetes/kubernetes), and the project pins stable releases.
- **Drop the entry of CVE-2026-78661.** Rejected: the requirement "The MCP ignore file holds the kubectl x/net entry" of `mcp-server-image` asks for it, and the Trivy DB of CI can differ from the local DB that does not report it.
- **Build kubectl from source with newer x/net and x/text.** Rejected: a custom build is a tool to build and keep (AGENTS.md rule 3), and the renewal stays in the cap.

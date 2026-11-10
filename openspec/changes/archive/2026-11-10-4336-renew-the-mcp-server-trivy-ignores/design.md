# Design

## What this change delivers

The change takes the fixes that exist (a bump of the two pins) and renews only the three findings that no release fixes. SECURITY.md ("A Finding with No Fix") asks for a bump when a fix exists, and for a renewal of 3 days otherwise, to 14 days in all.

## The cap

The entries first appeared in the commit of #4182 on 2026-11-08, with `exp:2026-11-11`. Renewal to 2026-11-14 is the first. The last renewal that stays within the cap ends on 2026-11-22. After that, the owner decides.

## Rejected alternatives

- **Renew all five entries.** Rejected: two findings have a fix in a released version.
- **A newer pre-release or a build from source.** Rejected: kubectl 1.38.0-beta.0 is a pre-release, and a custom build is a tool to build and keep (AGENTS.md rule 3).
- **Remove kubectl and helm from the image.** Rejected: the mcp-server image installs them on purpose (#3220).

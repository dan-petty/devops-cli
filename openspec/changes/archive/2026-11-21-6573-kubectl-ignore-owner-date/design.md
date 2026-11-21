# Design

## Decisions

- **The owner date.** SECURITY.md "A Finding with No Fix" limits an agent renewal to 14 days in all, and says that an entry that the owner names with another date keeps that date. On 2026-11-21, the owner gave 2026-12-15 for the kubectl entries.
- **All four kubectl entries get the same date.** CVE-2026-56851 and CVE-2026-97054 expire on 2026-11-22, and kubectl v1.37.2 holds all four findings. One date lets one kubectl bump delete all four entries.
- **A separate renewal issue.** #6084 stays open until a stable kubectl release holds the fixes. This pull request closes #6573.

## Rejected alternatives

- **Renew to 2026-11-22 only, the agent limit.** Rejected: the check fails again on 2026-11-22, and the owner gave a date.
- **Bump kubectl to v1.38.0-beta.0.** Rejected: it is a pre-release, and #6084 asks for a stable release.
- **Build kubectl from source with newer x/net and x/text.** Rejected: a custom build is a tool to build and keep (AGENTS.md rule 3).

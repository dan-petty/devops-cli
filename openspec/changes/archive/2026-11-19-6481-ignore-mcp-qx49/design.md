# Design

## Decisions

- **Ignore for 3 days, because no release holds a fix.** SECURITY.md "A Finding with No Fix" asks for a bump on the day that a fix is released, and for a 3-day entry otherwise. Semgrep 1.186.0, the newest release, requires `mcp==1.29.0`, so the entry ends on 2026-11-22. A renewal needs new proof, up to 14 days in all.
- **The narrowest scope.** The entry names the advisory id and the one file that pins `mcp` 1.29.0, as the four older `mcp` entries do.
- **A tracking issue that stays open.** This pull request closes #6481. The entry names #6480, which stays open until a Semgrep release takes `mcp` 1.30.0 or later.

## Rejected alternatives

- **Pin `mcp` 1.30.0 in `semgrep.txt` by hand.** Rejected: Semgrep requires `mcp==1.29.0`, so the file then holds a set that its resolver does not give, and `semgrep.txt` is compiled from the pinned Semgrep, not edited (#3988).
- **Remove Semgrep from the tools lock.** Rejected: the review sandbox runs Semgrep, and a change of that scope needs its own issue.

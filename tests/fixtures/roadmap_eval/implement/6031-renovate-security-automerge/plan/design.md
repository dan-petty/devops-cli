# Design

## Decisions
- GitHub auto-merge (`platformAutomerge`), so GitHub, not Renovate, decides the merge from the ruleset's required checks.
- The setting is in devops-cli's own config, not in the shared preset: a Service repository with no required checks (for example homelab) would merge with no gate.
- No update-type filter: the owner chose every security fix, major versions too.

## Rejected alternatives
- Automerge in the shared preset: it would reach repositories with no ruleset.
- Only non-major security fixes: the owner chose all security fixes.

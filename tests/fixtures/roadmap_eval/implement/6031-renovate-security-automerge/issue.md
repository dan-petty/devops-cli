## Problem
Renovate opens a pull request for each security fix (OSV advisories, `osvVulnerabilityAlerts` in `.github/renovate/base.json`; for example #6028 for certifi), and the pull request waits for a person to merge it. Owner, 2026-11-16: "id like to get renovate working and merging critical fixes automatically", for all security fixes, major versions too, after the required checks pass.

The repository allows auto-merge (`allow_auto_merge: true`). The ruleset `main` needs a squash merge, the checks `Static Analysis`, `Tests & Coverage` and `Semantic PR title`, resolved review threads, and 0 approvals; it has no bypass actor. So GitHub merges an auto-merge pull request only after those checks pass.

## Expected behavior
- In devops-cli's `.github/renovate.json`, each vulnerability-fix update (patch, minor or major) has `automerge: true` with `platformAutomerge: true` (GitHub auto-merge, squash), so it merges only when the required checks of the ruleset pass. Other updates keep waiting for a person.
- The shared preset `.github/renovate/base.json` does not turn automerge on, because a Service repository with no required checks (for example homelab) would merge with no gate.
- `AGENTS.md` keeps "only a person merges pull requests" with one exception: Renovate merges a security fix after the required checks pass (owner, 2026-11-16). The documents that state the merge rule say the same (`docs/SDLC.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/CLUSTER.md` Renovate section, ADR 0027 if it names the rule).
- A test reads the Renovate config and fails when automerge applies to anything other than vulnerability fixes, or when the shared preset turns automerge on.
- `renovate-config-validator` accepts the config.

## Related
- #4893, #4905, #6022, #6028, #6030.


<!-- devops-roadmap-record {"Effort": "Low", "Owner": "Agent", "Priority": "P2-Medium", "Status": "In Review", "Value": "Medium"} -->

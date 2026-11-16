# Proposal: #6031

## Why
Renovate opens a pull request for each security fix (OSV alerts of the shared preset; for example #6028), and the pull request waits for a person. Owner, 2026-11-16: "id like to get renovate working and merging critical fixes automatically", for all security fixes, major versions too, after the required checks pass. The repository allows auto-merge, and the ruleset `main` needs a squash merge, the checks `Static Analysis`, `Tests & Coverage` and `Semantic PR title`, resolved review threads and 0 approvals, with no bypass actor. Closes #6031.

## What Changes
- `.github/renovate.json` gets a `vulnerabilityAlerts` object with `automerge`, `automergeType: pr` and `platformAutomerge`. Renovate merges the object with the one of the shared preset (`mergeable: true` in the Renovate options), so the labels, the title prefix and the limits of the preset stay.
- `AGENTS.md` names the one exception to "only a person merges pull requests"; `docs/SDLC.md` and `docs/CLUSTER.md` say the same.

## Capabilities
- `renovate-service`: one new requirement.

## Impact
- A security fix of devops-cli merges after the required checks pass, and its release follows the normal release flow. A major security update can break an API; the required checks are the gate.

## Feasibility
Renovate 44.239.1 defines `vulnerabilityAlerts` as a mergeable object with defaults `schedule: []`, `minimumReleaseAge: null` and `prCreation: immediate`, and `platformAutomerge` defaults to true. `renovate-config-validator` accepts the config.

## Existing Tool Considered
Renovate automerge with GitHub native auto-merge. No code.

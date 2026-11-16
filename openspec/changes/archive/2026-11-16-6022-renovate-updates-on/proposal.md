# Proposal: #6022

## Why
The Renovate CronJob (#4905) ran as a lookup dry run. The first measured run on 2026-11-16 (#4909, Job `renovate-manual-1931`) worked from end to end: token, seed, 16 repositories found, devops-cli processed in 81 s, exit 0, no warning. Owner, 2026-11-16: "enable renovate", with the post-upgrade tasks off until #6020 keeps the installation token away from them. Closes #6022.

## What Changes
- The CronJob sets no `RENOVATE_DRY_RUN`, so Renovate opens update pull requests on each repository with a Renovate config (today devops-cli).
- `allowedCommands` is empty, and `.github/renovate.json` names no `postUpgradeTasks`. The `openspec` group and the devcontainer feature rule name their commands in `prBodyNotes`.
- The tests, the spec and `docs/CLUSTER.md` say that #6020 brings the tasks back.

## Capabilities
- `renovate-service`: two requirements change.

## Impact
- After the merge, Argo CD applies the CronJob and the ConfigMap; the next run (each 2 hours, at minute 17) opens pull requests. Each pull request of the `openspec` group or a devcontainer feature needs its commands run on the branch before the merge, or its checks fail.

## Feasibility
`renovate-config-validator` of Renovate 44.239.1 accepts the edited `.github/renovate.json`. With an empty `allowedCommands`, Renovate refuses each task command, so a repository config cannot run one.

## Existing Tool Considered
Renovate's own `allowedCommands` gate. Cost: a config change and two tests.

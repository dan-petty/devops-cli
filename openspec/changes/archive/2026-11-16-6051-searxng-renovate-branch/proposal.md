# Proposal: #6051

## Why
The shared preset puts every non-major Docker update in the group `container images`, so a SearXNG bump and the Renovate image patch came in one pull request (#6029). A person runs `devops k8s searxng-check` against each new SearXNG image on the cluster, so the other images waited for that step. The owner decided on 2026-11-16 (#6060) to keep this Renovate configuration and to drop the tests that read `renovate.json` values. Closes #6051.

## What Changes
- A rule at the end of the package rules of `.github/renovate.json` gives SearXNG the group `searxng` and `dependencyDashboardApproval: true`.
- `test_a_migration_waits_for_an_approval_on_the_dashboard` is removed: it read the approval rules of `renovate.json` and fails on the new rule.
- `docs/CLUSTER.md` describes the approval and the own branch.

## Capabilities
- `searxng-renovate-updates`: a new capability for how Renovate proposes a SearXNG update.

## Impact
- A SearXNG tag waits on the Dependency Dashboard until a person approves it, then comes alone. The other container images keep their group.
- PR #6069 changes the SearXNG note and the existing SearXNG rule; this change adds a separate rule at the end, so the two pull requests touch different lines.

## Feasibility
- `renovate-config-validator --strict --no-global` of `renovate@44.239.1`, the version of the CronJob, accepts both files.
- A local Renovate 44.239.1 run (`--platform=local --dry-run=lookup`) gave the branches `renovate/patch-searxng` and `renovate/searxng` for SearXNG, and `renovate/patch-container-images` for the Renovate image alone.
- `dependencyDashboardApproval` holds a whole branch when one update of it needs approval, so SearXNG needs its own group.

## Existing Tool Considered
Renovate `packageRules` with `groupName` and `dependencyDashboardApproval` cover the need. The change adds no code; `renovate-config-validator` checks the form.

# Proposal: #6054

## Why
Renovate gives a Helm chart update the prefix `chore(deps):`. Each chart update must also move the version of its release in `HELM_RELEASES_BY_STACK`, which is runtime code, and `chore` is hidden in `release-please-config.json`. So `Semantic PR title` refused the update when a person or an agent completed it, as on PR #6046. The owner decided on 2026-11-16 (#6060) to keep this Renovate configuration and to drop the tests that read `renovate.json` values. Closes #6054.

## What Changes
- A rule of `.github/renovate.json` gives each update of the `helm` datasource the prefix `fix(deps):`.
- The coupled group `dcgm-exporter` (chart and image) sets the same prefix, because a group takes the prefix of its first update.
- `docs/SDLC.md` names the prefix, and says which checks a chart update still fails.

## Capabilities
- `release-concurrency-and-renovate`: a requirement is added for the prefix of a chart update.

## Impact
- release-please adds a changelog line for each chart update, so a release ships the new chart version of `deploy-stack`.
- PR #6069 leaves the Renovate line of `docs/SDLC.md` to this change, so the two pull requests do not conflict.

## Feasibility
- The `Semantic PR title` run of PR #6046 (job 133643314532) refused `chore` for `src/devops_cli/commands/k8s/stack_lifecycle.py`; the title `fix(deps): update helm charts (patch)` passed, and #6046 merged with it.
- `renovate-config-validator --strict --no-global` of `renovate@44.239.1` accepts both files.

## Existing Tool Considered
Renovate `packageRules` with `commitMessagePrefix` cover the need, as the rule for the service image base does. The change adds no code; `renovate-config-validator` checks the form.

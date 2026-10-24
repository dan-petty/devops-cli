# Proposal

## Why

Issue #1752 asked which checks gate a merge into `main`, whether a merge queue serializes the merges, what runs locally before a push, and what only the owner can change. Every push ran the full `uv run devops ci` in the pre-push hook, and the repository required no check. The owner answered the questions on 2026-10-22. No document records the answers.

## What Changes

- Add `docs/adr/0014-required-checks-gate-the-merge-and-the-pre-push-hook-runs-the-fast-static-checks.md`. It records the decision: the three required checks of `main` with no strict policy and no merge queue, the fast static checks in the pre-push hook, the full `devops ci` as a manual command, the Copilot review on request, the cached verdict question and the owner steps. It gives the measured times and the consequences.
- Add a first line to ADR 0004 that names ADR 0014, as ADR 0012 did for ADR 0001.
- The change adds a decision record and changes no command, option, message, workflow or hook. No consumer observes a different behavior, so it has no spec delta and sets `skip_specs: true`.
- The pre-push hook and the documents that describe it change in #2110, not here.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `docs/adr/0014-required-checks-gate-the-merge-and-the-pre-push-hook-runs-the-fast-static-checks.md`: the new decision record.
- `docs/adr/0004-ci-is-the-authoritative-gate.md`: the amendment line.

## Feasibility

Read-only checks on 2026-10-24:

- `uv run devops gh api repos/dan-petty/devops-cli/rulesets` lists one ruleset, `main` (21466414). `uv run devops gh api repos/dan-petty/devops-cli/rulesets/21466414` shows the required checks `Static Analysis`, `Tests & Coverage` and `Semantic PR title`, no bypass actor, no `merge_queue` rule and no `copilot_code_review` rule. It also shows `strict_required_status_checks_policy: false`. ADR 0012 read the policy as on on 2026-10-22. On 2026-10-24 the owner said that the policy stays off, because the status of the release pull request shows a defect on `main`.
- `.github/workflows/ci.yml`: `Static Analysis` runs `uv run devops ci --check --no-cache --skip test,outdated`, and `Tests & Coverage` runs `uv run devops ci --check --no-cache --only test`. Together they run every check of `devops ci` but `outdated`.
- The jobs of the 25 latest passing pull request runs of `ci.yml` on 2026-10-24 (`uv run devops gh api repos/dan-petty/devops-cli/actions/runs/<id>/jobs`): `Static Analysis` took a median of 105 seconds and `Tests & Coverage` a median of 291 seconds. No job waited more than 4 seconds for a runner.
- `uv run devops gh api repos/dan-petty/devops-cli/pulls/<n>/reviews` returns no review for #2105, #2109 and #2112.
- GitHub's changelog of 2023-07-12 limits the merge queue to the GitHub Enterprise Cloud plan and to public repositories that organizations own. A user account owns this repository.
- GitHub's documentation of the automatic Copilot review names three places: a personal Copilot setting, a repository ruleset rule and an organization ruleset rule.

## Existing Tool Considered

GitHub rulesets (required status checks) are the open tool for the merge gate, and pre-commit is the open tool for the pre-push hook. The decision uses both as they ship. A merge queue is not available to a repository that a user account owns. This change adds a document and deletes no code.

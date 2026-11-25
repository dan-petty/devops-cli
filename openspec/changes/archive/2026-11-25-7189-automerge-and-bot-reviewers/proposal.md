# Proposal: #7189

## Why

Automated pull requests across `devops-cli` and the Service repositories do not consistently enable automerge or request `@dan-petty` as a reviewer (#7189). In `.github/renovate.json`, the `seaweedfs` rule sets `"automerge": false`. In `.github/workflows/release.yml`, `release-please` enables auto-merge but does not request a review from `dan-petty`. In `src/devops_cli/`, automated roadmap pull requests (`roadmap/steps/open.py` and its callers `open_row.py`, `stage.py`, `implement_phases.py`, and `commands/roadmap_step_open.py`) and onboarding template pull requests (`github/onboard/template_pr.py`) do not request the repository owner as reviewer, leaving private Free repositories without a review request even when `CODEOWNERS` exists.

## What Changes

- Remove `"automerge": false` from the `seaweedfs` package rule in `.github/renovate.json` and update `k8s/README.md` so Renovate merges approved SeaweedFS updates once checks pass.
- Add a step in `.github/workflows/release.yml` (`Request review on the release pull request`) that requests `dan-petty` via GitHub REST `POST /repos/{owner}/{repo}/pulls/{pull_number}/requested_reviewers` when the PR author is not `dan-petty` and `dan-petty` is not already requested.
- Extend `CreatedPull` (`user.login` as `author`, `requested_reviewers`) and add `missing_pull_reviewers` and `GitHubClient.request_pull_reviewers` in `src/devops_cli/github/client.py`.
- Add `reviewers` to `OpenRequest` in `src/devops_cli/roadmap/steps/open.py`, request missing non-author reviewers after draft creation, pass `(RepoRef(repo).owner,)` from `open_row.py`, `stage/stage.py`, `implement/implement_phases.py`, and `commands/roadmap_step_open.py`, and document the write in `roadmap/request_plan.py` and `lang/en/messages.py`.
- Add route `template-pull-reviewers` (`RouteOwner.TEMPLATE_PULL`) in `github/onboard/routes.py` and request `ctx.options.repo.owner` in `github/onboard/template_pr.py` when the pull author differs and is not already requested.

## Capabilities

- `roadmap-stage/open`: Request repository owner as reviewer on newly opened automated roadmap pull requests when not author or already requested (#7189).
- `repos-onboard`: Request repository owner as reviewer on non-owner template pull requests through `template-pull-reviewers` (#7189).
- `release-concurrency-and-renovate`: Request `dan-petty` on release pull requests and keep Renovate automerge active across all package rules (#7189).

## Impact

- Every automated pull request opened by Renovate, `release-please`, roadmap jobs, or `devops repos onboard` requests `@dan-petty` when opened by a non-owner account (without sending invalid self-review requests when the owner opens the pull request), and Renovate's `seaweedfs` rule no longer suppresses automerge.

## Feasibility

Verified against GitHub REST pull request review behavior (`tests/support/github_repository.py`: requesting the PR author returns HTTP 422), existing `.github/workflows/release.yml` App token permissions (`permission-pull-requests: write`), `tests/invariants/test_workflow_contracts.py`, and `renovate-config-validator --strict --no-global .github/renovate.json`.

## Existing Tool Considered

Uses GitHub REST `requested_reviewers` via `GitHubClient`, `gh api` in `.github/workflows/release.yml`, and Renovate's shared preset `github>dan-petty/infra//renovate/base` rather than running an external polling bot or separate workflow. This extends existing code paths across `client.py`, `open.py`, `template_pr.py`, `request_plan.py`, `.github/workflows/release.yml`, and `.github/renovate.json` (~15k tokens, ~45 minutes).

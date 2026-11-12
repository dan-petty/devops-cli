# Proposal: #4637

## Why

The release pull request changes only `.release-please-manifest.json`, `CHANGELOG.md`, `pyproject.toml` and `uv.lock` (#4637). `pyproject.toml` and `uv.lock` are image inputs, so each push to it starts the image builds, the Service Image Tests and the advisory checks. On the head of #5054, a push started 18 jobs, and 12 of them were these jobs. On 2026-11-11, the next merge cancelled 17 of the 24 `CI Quality Gate` runs and 7 of the 12 `Service Image Tests` runs of the release pull request. `release.yml` already builds, starts and scans each image before it publishes it. The account runs at most 20 hosted jobs at one time, so each of these jobs makes the queue of the other pull requests longer. Owner decision O3 of the CI audit (2026-11-11): the release pull request runs only the required checks.

## What Changes

- Each job that no rule of the `main` ruleset reads skips the release pull request: `Service Image`, `Runner Image`, `MCP Server Image`, `Changed-Test Independence` and `Design Tokens` in `ci.yml`, `DevContainer Image` in `devcontainer-image.yml`, and the six `Service Image Tests` shards in `service-image-test.yml`. The condition is `!(startsWith(github.head_ref, 'release-please--') && github.event.pull_request.head.repo.full_name == github.repository)`. A branch of a fork with such a name runs every job.
- `Static Analysis`, `Tests on Main`, `Tests & Coverage`, `Semantic PR title` and the CodeQL analysis still run. #4639 already skips the test shards on the release pull request, and `Tests on Main` reads the test run of `main`. A push to the release pull request starts 6 jobs (from 18).
- A new invariant test lists the jobs that a push to the release pull request starts. It allows only the required checks, the jobs that they need, the CodeQL jobs, and three jobs that do not run on that pull request. So a new job, or a job that moves to a workflow of its own (#4658), fails the test until it gets the condition.
- `docs/SDLC.md` says where the release pull request runs no job, and the status note of ADR 0004 names the facts that the issue found missing.
- The change alters CI workflows, tests and documents only. No consumer of `devops` sees a change, so the change has no spec delta (`skip_specs: true`).
- `release.yml`, the release-please trigger and the required checks do not change. The change fits one pull request.

## Capabilities

None. The change alters CI workflows and documents only.

## Impact

- A merge costs 12 fewer jobs when the release pull request run ends. The pull request comment gives the runner-minutes.
- A defect that only an image build of the combined `main` shows appears at publish time in `release.yml`, not on the release pull request. The release job of that image then fails before it tags the image.
- The release merge guard (`src/devops_cli/release/merge_candidate.py`) refuses only a check that failed or was cancelled. A skipped job does not block the scheduled merge.

## Feasibility

- `uv run devops gh api repos/dan-petty/devops-cli/pulls/4964/files` lists the four files. #5054 changes the same four files. `release-please-config.json` writes the version of `uv.lock` as an extra file.
- `uv run devops gh api repos/dan-petty/devops-cli/commits/<head of #5054>/check-runs` gives 18 jobs of GitHub Actions that start, 4 skipped jobs and the code scanning results. The 12 jobs of this change are 12 of the 18.
- `uv run devops gh api repos/dan-petty/devops-cli/rules/branches/main` gives the required checks `Static Analysis`, `Tests & Coverage` and `Semantic PR title`, the code scanning rule for CodeQL, and no strict policy.
- GitHub documents `github.head_ref` as the source branch of a `pull_request` run and as empty for other events, so a push, the schedule and a manual run keep each job. A job that its `if` skips reports `skipped` and takes no runner.
- The plan of the audit asked to mark ADR 0004 as superseded by ADR 0014. ADR 0014 says that ADR 0004 still holds that CI is the authoritative gate, and `devops_cli.roadmap.adr` reads a note with "Amended ... ADR 0014" as the status of ADR 0004. That note exists since #2118, so the acceptance line holds on the base. The note now also says that `update-prs.yml` does not exist and that the release pull request runs only the checks that the ruleset reads. ADR 0025 asks for a note at the top, not for an edit of the record.
- The audit measured the path checks in `ci.yml`. #4653 moved them to workflows of their own with a `paths` filter, and no release file is in these filters, so they need no condition. #4658 moved `DevContainer Image` to `devcontainer-image.yml`, whose filter holds `pyproject.toml` and `uv.lock`, so that job gets the condition.

## Existing Tool Considered

The GitHub Actions job condition `if` with `github.head_ref` (native) covers the need. No new tool, and no internal code is deleted. The test reuses the helpers `_starts_on`, `_needs` and `_runs` of `tests/invariants/test_workflow_contracts.py` and `RELEASE_FILES` of the release merge guard.

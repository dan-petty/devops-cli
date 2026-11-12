# Proposal: #4653

## Why
Rule Pack Tests, Docs Site Build, Image Pins and Third-Party Image Scan are jobs of `ci.yml` that test their paths in a step. So each one takes a runner on each push to a pull request, also when it has no work. In 94 PR runs of 2026-11-11, each of the four jobs started 94 times, and they did work in 0, 48, 15 and 0 runs. Each job waited 8.1 to 9.1 minutes in the queue on average for a median of 4 to 10 seconds of idle work (measured). The account runs at most 20 hosted jobs at one time, so each job that does no work makes the queue of each pull request longer. None of the four is a required check. Closes #4653.

## What Changes
- Each of the four jobs moves from `ci.yml` to a workflow of its own: `rule-pack.yml`, `docs-site.yml`, `image-pins.yml` and `third-party-image-scan.yml`. Each job keeps its job id and its check name.
- Each workflow runs on `pull_request` into `main` (opened, synchronize, reopened) with the native `paths` filter. The paths are the paths of the old step filter, and the workflow file in place of `ci.yml`. A change to `ci.yml` thus starts none of them.
- The step filters go: the `git diff` step of Rule Pack Tests and the `dorny/paths-filter` steps of the other three. The jobs lose `pull-requests: read`, which only the filter used, the `if` on the event, and the full history of the Rule Pack checkout.
- Each workflow has a concurrency group for each ref that cancels the run of an older head, and repeats the `env` of `ci.yml` that its job needs.
- The parity allowlist of `tests/commands/test_ci.py` loses the steps of the moved jobs. The contract tests read the new workflows.
- The specs `crawl4ai-service` and `k8s-image-pins` name the new workflow files and their `paths` filters, because the old requirements name `ci.yml`.
- `docs/SDLC.md`, `docs/_config.yml`, the comment of `pages.yml` and the reason of `semgrep` in `src/devops_cli/roadmap/runner_tools.py` name the new files.

## Capabilities
- Modified: `crawl4ai-service` (The scan of the third-party image only reports).
- Modified: `k8s-image-pins` (The CI job checks a pull request that changes the pins).

## Impact
- A push to a pull request starts a job of these four checks only when it changes a path of its filter. In the window above that is 0.67 jobs for each run, from 4.
- A pull request that changes no path of a filter shows no check of that workflow. None of the four is required, so no ruleset changes and no merge waits for a missing check.
- A change to `ci.yml` alone no longer runs the four checks. A change to a workflow file runs its own check.
- The third-party scan stays report-only: its Trivy step exits 0.
- The change fits one pull request.

## Feasibility
- GitHub documents that `on.pull_request.paths` decides whether a workflow runs at all: when no changed file matches a pattern, the workflow does not run ("Workflow syntax for GitHub Actions", `on.<push|pull_request|pull_request_target>.<paths|paths-ignore>`). For a pull request it lists the changed files with a three-dot diff, from the merge base to the head. When a matching file is not in the first 3,000 files of the diff, the workflow does not run. The same page says that a check of a workflow that the filter skips stays "Pending", and a pull request that requires that check cannot merge.
- `fail-to-pass.yml` and `service-image-test.yml` on `origin/main` already use this filter.
- The job data of 94 PR runs of `ci.yml` on 2026-11-11 (05:28Z to 13:04Z), read with `devops gh api repos/<owner>/<repo>/actions/runs/<id>/jobs`, gives the counts above. The work step of a job counts as work when its conclusion is not `skipped`.
- The rules of `main` (`devops gh api repos/<owner>/<repo>/rules/branches/main`) require the status checks Static Analysis, Tests & Coverage and Semantic PR title, and the CodeQL code scanning results. None of the four checks is required, so a skipped workflow blocks no merge.
- `devops review rules test --check` reads the rule pack and `rules.lock` and no git history, so the checkout needs no full history.

## Existing Tool Considered
The native `on.pull_request.paths` filter of GitHub Actions. A `dorny/paths-filter` step still takes a runner for each push, so it does not solve this. No new tool. The change deletes the `git diff` filter step of Rule Pack Tests and three `dorny/paths-filter` steps.

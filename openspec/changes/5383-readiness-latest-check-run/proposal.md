# Proposal: #5383

## Why
`devops pr ready`, `devops pr check-readiness` and the roadmap readiness rows count a failed check run that a newer run of the same check replaced (#5383). Each event of a pull request starts its workflows in a new check suite, and `GET /repos/{owner}/{repo}/commits/{ref}/check-runs` lists the latest run of a check in each suite. So a head commit can hold the failed run of a push beside the passed run of a close and reopen. The REST reader `_fetch_check_runs_from_rest` in `src/devops_cli/github/check_verdict.py` drops only a cancelled run that a newer run replaced, and keeps each failure. On 2026-11-13, `devops pr ready 5357` refused with "The check Fail-to-Pass Check failed.", but the latest run of each check passed or was skipped, and `devops gh pr checks 5357` showed the check as passed.

## What Changes
- `_without_replaced_cancellations` becomes `_latest_run_of_each_check`. For each check, the reader keeps only the latest run, whatever its conclusion. A check is a name and the id of the app that reports it. The time of a run is its `started_at`, else its `completed_at`. A run with no time stays, and each run at the latest time of its check stays.
- A newer failed or cancelled run still fails its check, and a newer run that still runs keeps its check pending.
- `read_check_runs` and `read_commit_checks` both use the reader. So `devops pr ready`, `devops pr check-readiness`, `devops pr monitor`, `devops pr evidence`, the roadmap readiness rows (stage ready, the implement watch, the failed checks of the inbox), the branch update and the release merge candidate judge the same runs.
- `docs/roadmap/inbox.md` says that a draft of a job is listed when a check of its head commit failed in its latest run.
- The verdict of `devops pr ready` and `devops pr check-readiness` is observable, so the change has a delta of the capability `pr-merge-readiness`.

The change fits one pull request.

## Capabilities
- `pr-merge-readiness` (modified): ADDED requirement "Only the latest run of each check counts".

## Impact
- A pull request whose old run of a check failed and whose newer run of that check passed is ready. `devops pr ready` marks it ready with no `--force`.
- A head commit whose latest run of a check failed, was cancelled or still runs gets the same verdict as before.
- The inbox does not list a draft of a job for a failed run that a newer run replaced.
- No setting, command, option, message or manifest changes.

## Feasibility
- `uv run devops gh api 'repos/dan-petty/devops-cli/commits/f7064d0f0/check-runs?per_page=100'` on 2026-11-13 gave 45 runs of 25 checks. 20 checks have two runs, each in its own check suite. Fail-to-Pass Check has a failed run (started 04:32:51Z, suite 117430079597) and a passed run (started 06:41:35Z, suite 117467460684). The latest run of each check passed (20) or was skipped (5). The answer, cut to the fields that devops-cli reads, is in `tests/fixtures/github/check_runs_pr_5357_head.json`.
- `uv run devops pr check-readiness 5357` at origin/main `4ef7c6f11` printed "PR #5357 has 1 failing check(s): Fail-to-Pass Check." beside the draft blocker.
- `uv run devops gh pr checks 5357`, which reads `gh pr checks --json`, showed one Fail-to-Pass Check row with `pass`. gh shows only the latest run of a check.
- `git grep` on origin/main: `_fetch_check_runs_from_rest` is the one reader of the REST check runs. `read_check_runs` and `read_commit_checks` call it, and `assess_merge_readiness` in `src/devops_cli/github/merge_readiness.py` calls one of the two. So one change makes `pr ready`, `check-readiness` and the readiness rows agree.
- The new tests failed on origin/main. On the recorded head, `pr ready` exited 1 with "The check Fail-to-Pass Check failed.", as it did on #5357.

## Existing Tool Considered
- `gh pr checks` shows only the latest run of a check across check suites. But it reads GraphQL through the `gh` binary, and the Service reads check runs with the App token through the REST session, with `checks: read` only (#2865). The REST API has no filter across check suites: `filter=latest` works in each suite only. So no open tool covers the REST read.
- The change edits the existing filter and adds no module. Cost: about 80,000 tokens and 1 hour to build, and nearly 0 to keep.
- Internal code that the change deletes: `_without_replaced_cancellations` in `src/devops_cli/github/check_verdict.py`, and its test, which read the checks through a `MagicMock` runner.

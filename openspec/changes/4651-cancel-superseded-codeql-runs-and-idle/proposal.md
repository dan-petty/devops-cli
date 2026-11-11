# Proposal: #4651

## Why
Three workflows start jobs that do no useful work. The account runs at most 20 hosted jobs at one time, so each such job makes the queue of each pull request longer. Closes #4651.

- `codeql.yml` has no concurrency group and no `timeout-minutes`, so a job can run for the default of 360 minutes. In the last 100 runs, 0 runs were cancelled, and 8 of 58 pull request runs continued after a newer push to the same branch had started a new run.
- `fail-to-pass.yml` starts on `edited`. In the last 100 runs, 24 runs repeat the head commit of an earlier run on the same branch, and 17 of them ran the replay job again. An edit of the body changes neither the replay nor the job condition.
- `cleanup-devcontainer.yml` starts on each closed pull request to delete `pr-<n>` tags, but no workflow pushes such a tag (#1858, ADR 0012). The last 100 runs span 27.9 hours, and 99 of them came from a closed pull request.

## What Changes
- `codeql.yml`: a concurrency group with `cancel-in-progress: true`. A pull request uses one group for each ref, so a newer push cancels the analysis of the old head. A push to `main` and the schedule each use a group of their own run, so each commit of `main` is analysed as before. The `analyze` job gets `timeout-minutes: 15`.
- `fail-to-pass.yml`: the job does not run for an edit that changes neither the title nor the base. The run of such an edit uses a concurrency group of its own, so it cannot cancel the replay of the head. An edit of the title or the base runs the job again, as before.
- `cleanup-devcontainer.yml`: the `pull_request` `closed` trigger and the script lines that only that trigger used are removed. The daily schedule and `workflow_dispatch` stay.
- `tests/invariants/test_workflow_contracts.py`: the contract of the fail-to-pass job condition and of its concurrency group reads the new form.
- `CONTRIBUTING.md`: the fail-to-pass entry says that an edit of the body alone does not start the check again.
- The change alters only CI workflows, a test and a document, which no consumer of devops-cli observes, so it has no spec delta (`skip_specs: true`).

## Capabilities
- None.

## Impact
- `.github/workflows/codeql.yml`, `.github/workflows/fail-to-pass.yml`, `.github/workflows/cleanup-devcontainer.yml`, `tests/invariants/test_workflow_contracts.py`, `CONTRIBUTING.md`.
- The required checks (`Static Analysis`, `Tests & Coverage`, `Semantic PR title`) and the code scanning rule do not change. CodeQL still analyses each pull request head and each push to `main`.
- The change fits one pull request.

## Feasibility
- GitHub workflow syntax reference (`concurrency`): "By default, any existing `pending` job or workflow in the same concurrency group will be canceled", and `cancel-in-progress: true` also cancels the running one. So a shared group for `main` would drop the analysis of a pending commit even with `cancel-in-progress: false`, and a group of its own run keeps each commit of `main`.
- GitHub webhook reference: the `edited` action of `pull_request` means "The title or body of a pull request was edited, or the base branch of a pull request was changed". The `changes` object holds the old `title`, `body` or `base`, so an expression can tell a body edit from a title or base edit.
- The replay reads the title (job condition) and `github.base_ref` (`BASE_REF`), and no body (`test_workflow_contract_fail_to_pass`).
- `_without_replaced_cancellations` in `src/devops_cli/github/check_verdict.py` drops a cancelled check run that a later run of the same check replaced (#1599). If a body edit run shared the group of the replay, it would cancel the replay, and only the skipped run would stay. So the body edit run needs a group of its own.
- The check runs API with `filter=latest` returns the check runs of each check suite: for head commit `2d768452` of a fix pull request it returned both the `success` and the `skipped` run of `Fail-to-Pass Check`. So the skipped run of a body edit does not hide the result of the replay.
- No workflow pushes a `pr-<n>` tag: the devcontainer job of `ci.yml` pushes by digest (`Build and Push DevContainer Image by Digest`), and `git grep` finds `pr-` tags only in `cleanup-devcontainer.yml`.
- Measured with the Actions API on 2026-11-11 (last 100 runs of each workflow): the CodeQL `analyze` jobs of 50 runs took a median of 58 s and a maximum of 212 s, so 15 minutes is more than 4 times the maximum. The cleanup jobs took a median of 16 s.

## Existing Tool Considered
- GitHub Actions `concurrency`, `timeout-minutes` and the `github.event.changes` payload cover the need. The change builds no tool.
- The change deletes the closed pull request path of `cleanup-devcontainer.yml` (the `pull_request` trigger, `CLOSING_PR_NUMBER` and the block that removed the closing tag from the exclusion list).

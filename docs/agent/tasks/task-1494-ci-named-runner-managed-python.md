# Task: CI jobs run on a named ubuntu-24.04 runner and always use uv's managed Python, never the runner's own Python (#1494)

**Issue**: [#1494](https://github.com/dan-petty/devops-cli/issues/1494)
**Status**: Done
**Milestone**: v0.2.32
**Priority**: P2-Medium (set by intake on 2026-10-09)
**Scope**: type/bug, scope/ci

## Description

GitHub moves the `ubuntu-latest` label to Ubuntu 26.04 between 2026-10-19 and 2026-11-19 (actions/runner-images#14748), and every job of ours showed the migration notice. Nine `runs-on` selections used `ubuntu-latest`: five in `ci.yml`, two in `release.yml`, one in `cleanup-devcontainer.yml`, and the non-swift arm of a template expression in `codeql.yml`, whose matrix has only `actions` and `python`.

On 26.04, CI would stop using the pinned Python:

- Both setup-uv steps (the `setup-toolchain` composite action that `ci.yml` uses, and `release.yml`'s release job) pass `python-version: "3.14"`. setup-uv exports it as `UV_PYTHON=3.14`, which overrides `.python-version` (3.14.7).
- Ubuntu 24.04's own Python is 3.12, so uv installs its managed CPython 3.14.7. Ubuntu 26.04 ships Python 3.14 as `/usr/bin/python3`. setup-uv's cache key includes the OS version, so the first 26.04 run of each job has no managed Python, and uv's default preference takes the matching system interpreter. setup-uv then skips the Python cache save, so every later run stays on Ubuntu's build.
- Reproduced with uv 0.12.16, offline, with an empty `UV_PYTHON_INSTALL_DIR`: `UV_PYTHON=3.14 uv python find --system` returns the system interpreter. With `UV_MANAGED_PYTHON=1`, uv finds no interpreter in managed installations and refuses the system one, while an explicit interpreter path (`uv python find /usr/bin/python3`) still works.
- uv refuses to run when `UV_MANAGED_PYTHON` and `UV_PYTHON_PREFERENCE` are both set ("cannot be used with `--python-preference`"), so only `UV_MANAGED_PYTHON` is set, not the `UV_PYTHON_PREFERENCE=only-managed` spelling setup-uv's warning names.

The issue asked for `ubuntu-26.04`, but actionlint 1.7.12, which `devops ci` and the pre-push hook run, rejects `ubuntu-26.04` as an unknown runner label (9 errors), and upstream actionlint has released nothing since 2026-03-30. By the owner's decision of 2026-10-09, every job names `ubuntu-24.04` instead. A named label is not migrated, so no job lands on 26.04 without review, and `UV_MANAGED_PYTHON` is already in place when the jobs move.

## Acceptance Criteria

- [x] No workflow job runs on `ubuntu-latest`. All nine selections name `ubuntu-24.04` with a comment linking #1501, and `codeql.yml`'s is a plain label.
- [x] `ci.yml` and `release.yml` set `UV_MANAGED_PYTHON: "1"` in their workflow-level `env`, which reaches the composite action's `uv sync` and every later `uv run`. `test_github_workflows_name_their_runner_and_use_managed_python` in `tests/test_ci.py`, next to `test_github_workflows_caching_configuration`, fails when a job's `runs-on` is a `-latest` label, or when a workflow that reaches setup-uv, directly or through a local composite action, lacks the setting. It failed on the tree before the change with the nine jobs, and fails when `ci.yml`'s setting is removed.
- [x] This repository's workflow runs no longer show the "ubuntu-latest label will migrate" notice, which GitHub shows for jobs that request `ubuntu-latest`. Runs on `main` (Renovate pull requests into `main`, the schedules, dispatches) use `main`'s workflows and show it until v0.2.32's release pull request merges.
- [x] actionlint 1.7.12 reports 0 errors on the workflows, and `uv run devops ci` passes.
- The move to `ubuntu-26.04` and its checks on 26.04 (managed CPython 3.14.7 and the `-python` cache save, the Tests & Coverage skip count, Docker 29 builds of the Service and DevContainer images, Trivy): moved to #1501, which waits for the workflow linter to accept the label.

## Deliverables

- [x] `.github/workflows/ci.yml`, `release.yml`, `cleanup-devcontainer.yml` and `codeql.yml`: `runs-on: ubuntu-24.04` in all nine jobs, each with a comment linking #1501.
- [x] `.github/workflows/ci.yml` and `release.yml`: workflow-level `env` with `UV_MANAGED_PYTHON: "1"`.
- [x] `tests/test_ci.py`: `test_github_workflows_name_their_runner_and_use_managed_python`.
- [x] `changelog.d/1494.md`.
- Replacing actionlint with a source that knows `ubuntu-26.04`: #1119.

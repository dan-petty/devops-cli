# Proposal: #4076

## Why
When `devops roadmap stage` creates a plan pull request, it creates a topic branch from `origin/main`. Implementation steps can run much later. During the delay, other changes merge into `main`. The topic branch stays at the commit where it branched. The job already fetches the default branch and rebases before the first step and before the push, aborting on conflicts. A person who debugs a branch needs an escape hatch to skip that fetch and rebase. Closes #4076.

## What Changes
1. Add `--rebase / --no-rebase` CLI flag to `devops roadmap implement` (defaults to `--rebase`).
2. Add `--no-rebase` to `runner_only_options` in `src/devops_cli/roadmap/implement/implement_outside.py` so workstation invocations with `--confirm` refuse it and name `devops k8s run-job --template runner`.
3. In `src/devops_cli/roadmap/implement/implement_run.py`, accept `rebase: bool = True` in `apply_implement`, `_implement_item`, and `_ItemRun`. When `rebase` is false, skip `_sync()` before the first step and before the push, and return `self._head()` in `_rebased_copy()`.
4. In `src/devops_cli/roadmap/implement/implement.py` and `src/devops_cli/roadmap/request_plan.py`, accept `rebase` in `dry_run_implement` and `implement_requests`, omitting the rebase request when `rebase` is false.
5. Update documentation and CLI reference.

## Capabilities
- Add `--rebase / --no-rebase` option to `devops roadmap implement`.
- Skip synchronization and rebase during implement when `--no-rebase` is passed.
- Runner-only enforcement for `--no-rebase`.

## Impact
- A person can debug an item branch in a runner without automatic rebase onto `main`.
- Unattended runs remain unchanged and always rebase onto `main`.

## Feasibility
Confirmed against `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/implement/implement_outside.py`, and `src/devops_cli/commands/roadmap.py`.

## Existing Tool Considered
Git rebase in `git_support.py`. Implementing the `--no-rebase` CLI option and wiring requires approximately 5,000 tokens to implement and test.

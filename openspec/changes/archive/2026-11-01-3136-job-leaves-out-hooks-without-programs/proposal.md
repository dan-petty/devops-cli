# Proposal

## Why

Issue #3136: the implement Job runs the hooks of the `pre-push` stage (#3112). The hook `devops-ci-workflows-pre-push` runs `devops ci --check --only actionlint,zizmor` when a commit changes a workflow file. The runner image holds no `actionlint` (#3111; `NOT_IN_RUNNER` records why), and no agent can install it. So the hook fails in the Job for every item that changes a workflow, the repair rounds run out, and the Job stops with no push. The independent review of #3112 proved the failure: the `actionlint` row fails on a PATH without the tool.

## Feasibility

- `.pre-commit-config.yaml` has the hook `devops-ci-workflows-pre-push` with `files: ^\.github/(workflows|actions)/`.
- `NOT_IN_RUNNER` in `src/devops_cli/roadmap/runner_tools.py` lists `actionlint`.
- `pre-commit validate-config` accepts the repository configuration with that one hook removed (17 of 18 hooks stay).
- `pre-commit` also reads a `SKIP` variable. The change edits the copy of the configuration instead: the Job already writes that copy for every hook run, so one place decides which hooks run, and the copy shows which hooks ran.

## Existing Tool Considered

`pre-commit` already reads the configuration the Job gives it with `--config`, and the Job already writes a copy of the default-branch configuration (#3043). So the change edits that copy. No new tool.

## What Changes

- `runner_tools.py` gets `HOOK_PROGRAMS` (hook id to the programs it runs) and `hooks_without_programs()`, which names the hooks whose program is not on PATH.
- `trusted_config` in `implement_hooks.py` leaves those hooks out of the copy it writes, and a repository that keeps no hook. The copy is the file text when no hook is left out.
- Tests: the copy has no such hook when its program is missing, is the same text when the program exists, and drops a repository with no hook left; `hooks_without_programs` follows the search path; each program of `HOOK_PROGRAMS` is in `NOT_IN_RUNNER`, and each hook id is in `.pre-commit-config.yaml`.
- The change modifies one requirement of `roadmap-implement-job`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job`: the requirement `Every hook run reads the configuration of the default branch` names the hooks that the Job leaves out.

## Impact

- The Job: an item that changes a workflow file now passes the `pre-push` hooks in the Job, and the checks of its pull request run the workflow checks.
- A person who adds a hook that runs a program from `NOT_IN_RUNNER` must add the hook to `HOOK_PROGRAMS`. No test finds the missing entry by itself; the Job's first failure shows it.

# Proposal

## Why

Issue #2041: #1847 made an OpenSpec change folder the record of every item and deleted the task files. Pull requests that were open before that switch still merged task files while #1847 ran its checks, so its decommission test had to accept them. The docs inventory kept the glob `docs/agent/tasks/task-*.md`, and the test allowed that one glob and `task-*.md` files in the directory. Readiness now refuses a pull request that does not archive its change, so no more task files can merge, and the allowance can go.

## What Changes

- Delete the five task files that merged after the switch: `task-1629-service-metrics-export-per-batch.md` (#2042), `task-1631-spend-series-and-serving-backend.md` (#2040), `task-425-outward-facing-capability-upstream-maturity-survey.md` (#2044), `task-2034-review-path-payloads-speed.md` (#2048) and `task-482-group-analysis-profiled-stage.md` (#2049). Git history keeps them.
- Remove the glob `docs/agent/tasks/task-*.md` and its comment from `CONST_DOCS_INVENTORY`.
- Remove `_LATE_TASK_FILES_GLOB` and make `test_the_task_files_are_decommissioned` strict again: the directory does not exist, and no code, test, manifest, GitHub file or hand-written document names it.
- The change alters no behavior that a consumer observes: it deletes records, one inventory entry that then matches no file, and a test allowance. So it sets `skip_specs: true`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/config/constants.py`, `tests/test_architectural_invariants.py` and `docs/agent/tasks/`.
- A pull request that is still open and adds a task file now also fails the decommission test, in addition to readiness. It converts its task file into a change folder when it updates from `main`.

## Feasibility

- On `main` at `ae4acafc`, `docs/agent/tasks/` holds four files, and `git log -- docs/agent/tasks` shows that #2040, #2042, #2044 and #2048 added them after #2020 (`26383175`).
- `git grep docs/agent/tasks -- src tests .github k8s` finds only the inventory glob in `src/devops_cli/config/constants.py`. The archived change of #425 names its task file in `tasks.md`, which is a record and is not scanned.
- With the strict test and the files still in the tree, `uv run devops ci test tests/test_architectural_invariants.py -k task_files` failed: the directory existed and `src/devops_cli/config/constants.py` named it.

## Existing Tool Considered

`git rm` deletes the files, and the existing decommission test, `test_the_task_files_are_decommissioned`, is the check. No new code is built. The change deletes the inventory glob, `_LATE_TASK_FILES_GLOB` and the allowance in the test.

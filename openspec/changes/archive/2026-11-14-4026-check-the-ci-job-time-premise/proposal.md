# Proposal

## Why

An item can state that a CI job stays under a duration, and the stage job plans it without reading the current duration. A false premise then reaches a plan pull request, as #2163 and pull request #3960 show (#4026).

## What Changes

- Add `src/devops_cli/roadmap/stage/stage_time.py`: `JobTimePremise`, `job_time_premise` and `job_time_failure`. The parse takes the check in a code span and its `under N s` limit from the item body; the verdict passes a mean equal to the limit, as `devops ci job-time` does.
- Add `_time_premise_of` to `stage.py`: before the planner call, the stage job reads the mean of the check's last 20 runs on the default branch, retries the read once, and returns the item to New with the evidence through the existing `FalsePremise` path.
- A read that fails twice raises `GitHubOperationError`, which records the item's `ci_infra` failure and leaves it Ready.
- Add `tests/roadmap/stage/test_roadmap_stage_time.py` for the parse, the verdict, the skip of the planner and the `ci_infra` failure.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/premise`: the stage job checks a stated CI job-time limit.

## Impact

- Code: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_time.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_time.py`
- Document: `docs/ROADMAP_WORKFLOW.md`

## Feasibility

- Read on `origin/main`, 2026-11-14. `src/devops_cli/ci/job_time.py:67:def check_job_time(` reads the runs, and `:53:def passes(` compares `mean_seconds <= limit_seconds`.
- `src/devops_cli/roadmap/stage/stage.py:2442:def _plan_each(` loops over the targets, catches the errors of the planner and makes a `FalsePremise` result.
- `src/devops_cli/roadmap/failure.py:152:CLASS_BY_EXCEPTION` maps `GitHubOperationError` to `FailureClass.CI_INFRA`.
- `uv run pytest tests/roadmap/stage` passes after the change.

## Existing Tool Considered

`check_job_time` already measures the job, and `devops ci job-time` already reports it. The change adds only the gate in the stage job: about 5,000 tokens to build and 300 a quarter to keep.

## Dependencies

None.

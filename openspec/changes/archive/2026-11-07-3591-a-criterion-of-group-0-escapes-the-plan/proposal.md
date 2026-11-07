# Proposal

## Why

#3591: a criterion with `Group 0` in `tasks.md` makes `StageCriterion` raise a pydantic `ValidationError`. `_criteria` in `src/devops_cli/roadmap/plan_read.py` builds the criterion outside any `try` block, so the error leaves `read_change`. `plan-check` and `plan-recheck` catch only `PlanReadError`, so each command ends with a traceback instead of a report.

## What Changes

- `_criteria` turns the `ValidationError` of `StageCriterion` into a `PlanReadError` for `tasks.md`. The reason is the one-line text of `_reasons`, as for a task group that the model refuses.
- A new message `plan_read_bad_criterion_model` in `src/devops_cli/lang/en/messages.py` names the criterion line and the reason.
- A new requirement of `roadmap-plan-check` states that the reader reports a criterion that the model refuses, and that plan-check and plan-recheck report it as a `read` problem.
- `docs/roadmap/plan-check.md` lists the criterion among the things that the read reports.
- `StageCriterion` is not changed. A group number names a task group, and the groups start at 1.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-plan-check`: the reader reports a criterion that the model refuses.

## Impact

- Code: `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/test_roadmap_plan_read.py`, `tests/roadmap/test_roadmap_plan_check.py`, `tests/roadmap/test_roadmap_plan_recheck.py`
- Documents: `docs/roadmap/plan-check.md`

## Feasibility

- The defect was confirmed in the code of origin/main. `read_change` calls `_criteria` before the `try` block that wraps `StageProposal`, and `_criteria` builds `StageCriterion(group=int(...))` with no handler. The validator of `StageCriterion` raises for a group below 1.
- #3482 (merged) turned the `ValidationError` of a task group into `PlanReadError` in `_read_group`. It did not cover `_criteria`, so the defect is still present.
- `plan_check.py` and `plan_recheck.py` catch `PlanReadError` only, so a `ValidationError` from `read_change` reaches the caller.
- No open pull request changes `plan_read.py`.

## Existing Tool Considered

- Pydantic already raises the error, and `_reasons` already renders it. The change adds no tool and no new helper.
- Relaxing `StageCriterion` to accept `Group 0` was rejected: it would hide a malformed plan. The change deletes no code. The cost to build, keep and fix is about 5 lines, under 500 tokens, and under 1 hour.

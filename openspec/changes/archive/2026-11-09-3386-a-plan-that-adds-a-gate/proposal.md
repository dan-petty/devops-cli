# Proposal

## Why

A plan that adds a gate can claim it refuses a defect that the gate does not refuse (#3386). The plan for #3308 is an example. Its Feasibility said the plan of PR #3260 claimed 40 while `SUMMARY_MAX_CHARS` is 60. The actual plan of PR #3260 gave `PLAN_SUMMARY_MAX_CHARS = 47` and said that the issue text says 40 and the schema says 60. The planned check skips a constant name that the staged tree does not define, so it cannot refuse that plan. The Feasibility quoted the staged constant and did not quote the defective plan text or test the rule against it. A plan that quotes only the staged value can pass every gate and still add a check that misses its own example. The plan check now ties a new gate to the defect that the gate refuses.

## What Changes

- In `src/devops_cli/roadmap/stage/stage_change.py`, when a plan changes `src/devops_cli/roadmap/stage/stage_eval_gates.py` or `src/devops_cli/roadmap/stage/stage_change.py`, require its Feasibility to quote the defective text that the gate must refuse in a code span.
- Require one gate task group test to hold the quoted code span and the phrase `fails on the base`.
- When the gate test skips a case, as indicated by `skip` or `skips`, require the plan to state that non-goal in its decisions, its rejected alternatives or its spec delta.
- Add `stage_problem_gate_defect_quote`, `stage_problem_gate_defect_test`, and `stage_problem_gate_non_goal` to `RoadmapMessages` in `src/devops_cli/lang/en/messages.py`.
- Add tests in `tests/roadmap/stage/test_roadmap_stage_plan.py` that refuse a gate plan with no defect quote, refuse a gate plan with no failing test, refuse a skipped case with no non-goal, and accept a gate plan with the defect quote and the failing test task.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A plan that adds or changes a gate quotes the defect the gate refuses in feasibility and gives a test task that fails on the base.

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_plan.py`

## Feasibility

- `src/devops_cli/roadmap/stage/stage_change.py` defines `content_problems`, `check_proposal` and the plan content rules.
- `src/devops_cli/roadmap/stage/stage_eval_gates.py` defines `_content_gate`, which calls `content_problems`.
- The paths cited in issue 3386 moved in commit `bff2f14fd` (#3897): `src/devops_cli/roadmap/stage_change.py` is at `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/stage_eval_gates.py` is at `src/devops_cli/roadmap/stage/stage_eval_gates.py`, and `tests/roadmap/test_roadmap_stage_plan.py` is at `tests/roadmap/stage/test_roadmap_stage_plan.py`. The staged paths exist in the staged tree.
- `code_spans` in `src/devops_cli/roadmap/step_files.py` extracts backtick spans from text lines.
- `RoadmapMessages` in `src/devops_cli/lang/en/messages.py` holds user-facing plan check messages.
- The first check of the implementation is `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_plan.py`.

## Existing Tool Considered

No open tool checks a plan against its own motivating example. The change reuses the existing plan check and needs no dependency. Estimated cost: 8,000 tokens to build, 2,000 tokens per month to keep and fix, and 1 elapsed day.

## Dependencies

None.

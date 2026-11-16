# Proposal: #4099

## Why
The implement runner stops a step when it modifies a path outside the plan (`_outside_plan_failure`, #3824). An agent can send a `plan-request` to amend the plan. In `src/devops_cli/roadmap/implement/implement_amend.py`, `_judge_path` permits only path renames where the basename matches. If an implementation needs an existing omitted file, such as a constants module or a test fixture, the agent cannot request adding that path to the group. The step stops with `FailureClass.OUTSIDE_PLAN` and requires human intervention. Closes #4099.

## What Changes
1. Support `add_path` as an allowed kind in `PlanRequest` with an optional `header` field (`Changes` or `Reads`).
2. Add `_judge_add_path` in `src/devops_cli/roadmap/implement/implement_amend.py`:
   - Validate that `new` exists in `tree.files`.
   - Validate that `new` does not sit under `openspec/`.
   - Validate that the group does not already hold `new` in a code span.
   - Refuse when `old` is provided on an `add_path` request.
   - Refuse when `header` is absent or the group holds no matching header line.
   - Append backticked `new` to the named header line (`Changes:` or `Reads:`).
   - Form an `Amendment` with kind `add_path`, empty `old`, and `new`.
3. Add unit test coverage in `tests/roadmap/implement/test_roadmap_implement_amend.py`.

## Capabilities
- `roadmap-plan-amendment`: Support bounded path additions to task groups in plan requests.

## Impact
- Enables automated recovery when an implement task needs to read or write an existing tracked file not listed in the original plan.
- No breaking changes; existing `path`, `command`, `task`, `group`, `scope`, and `premise` request forms remain unchanged.

## Feasibility
Confirmed against `src/devops_cli/roadmap/implement/implement_amend.py` and `tests/roadmap/implement/test_roadmap_implement_amend.py`.

## Existing Tool Considered
The change extends the existing `PlanRequest` parser and validator in `src/devops_cli/roadmap/implement/implement_amend.py`. Cost: 6,000 tokens and 0.25 elapsed days.

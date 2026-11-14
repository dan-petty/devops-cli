# Proposal: #3576

## Why

A group step that changes no file stops with class `plan_defect`, and its reason is the one sentence "The agent changed no file." The group may be too large or already done, and neither the reason nor the amendment kinds give the model or the service a way to ask for a smaller group. The owner decision of 2026-11-02 holds: a `plan_defect` stops at once unless the bounded amendment covers it. Closes #3576.

## What Changes

- The stop of a group step that changes no file names the group and asks for a smaller replacement, within the bounded amendment of #3057.
- `PlanRequest` accepts the kind `group`: the new text replaces the group when it keeps the group number, has fewer tasks, and names no path that the group does not name. A replacement that breaks a bound is refused with the reason.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-step/exit-checks`: The no-change stop names the group and asks for a smaller replacement.
- `roadmap-plan-amendment`: A plan request can replace a group with a smaller one.

## Impact

- Code: `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/roadmap/implement/implement_amend.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/implement/test_roadmap_implement_amend.py`, `tests/roadmap/implement/test_roadmap_implement_step.py`, `tests/roadmap/implement/test_roadmap_implement_step_failure_class.py`, `tests/roadmap/implement/test_roadmap_implement_step_attempts.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`, `tests/roadmap/implement/test_roadmap_implement_strays.py`

## Feasibility

Read on 2026-11-14 against `origin/main` at `04107728d`.

- The stop exists: `src/devops_cli/roadmap/implement/implement_step.py:1633:return _Failure(MESSAGES.roadmap.implement_stop_no_change, klass=no_change)`, and `:1630` chooses `PLAN_DEFECT` for a group step.
- The class reaches the trace: `src/devops_cli/roadmap/implement/implement_trace.py:217:def attempt` writes `fields["class"]` from the outcome.
- The amendment kinds are `path`, `command`, `task`, `premise` and `scope`: `src/devops_cli/roadmap/implement/implement_amend.py:29:Kind`.
- The parser and the bounds are one place: `judge` at `:245` replaces `target.text` and records the amendment bullet at `:284`.
- The new tests pass on the branch: `uv run devops ci test tests/roadmap/implement`.

## Existing Tool Considered

No open tool covers a bounded replacement of one group of a repository-specific plan, and #3057 already builds the amendment frame. The change extends its kinds and its stop reason, adopts no new dependency, and costs about 60 lines of code with about 120 lines of tests.

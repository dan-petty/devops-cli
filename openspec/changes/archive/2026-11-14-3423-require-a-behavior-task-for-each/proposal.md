# Proposal: #3423

## Why

A spec delta can add a scenario that no task tests, and the plan still passes. The plan of PR #3400 adds the scenario `A What Changes line below the least length` to a MODIFIED requirement, and no task adds a test for it, yet `devops openspec check` and every check of the pull request pass. The rule of #3321 refuses only a scenario that names code, so a scenario that names a field still passes. Closes #3423.

## What Changes

- `check_proposal` pairs each scenario of an added or modified requirement that names no code with a `behavior` group: the group's `test` names the scenario or the requirement, or its `verify` runs a test module that the group changes or creates. A plan with no such group is refused, with the scenario and its requirement in the problem.
- A scenario whose name the base spec of the capability already holds is exempt. The stage job, `devops roadmap plan-check` and `devops roadmap plan-recheck` give the base scenario names, as they give the base requirement names.
- The stage prompt states the rule.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/spec-delta`: A scenario that names no code needs a behavior task.

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/stage/stage_specs.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_request.py`, `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/roadmap/plan_check.py`, `src/devops_cli/roadmap/plan_recheck.py`, `src/devops_cli/lang/en/messages.py`
- Prompt: `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_scenario_evidence.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`, `tests/roadmap/stage/test_roadmap_stage_plan_check.py`

## Feasibility

Read on 2026-11-14 against `origin/main` at `04107728d`.

- The code rule sits beside the existing one: `src/devops_cli/roadmap/stage/stage_change.py:1049:_scenario_problems` and `src/devops_cli/roadmap/stage/stage_change.py:1082:stage_scenario_untested_code`.
- The base spec reader holds the requirement names: `src/devops_cli/roadmap/stage/stage_specs.py:29:class BaseSpec`; it does not hold scenario names yet.
- The gates take the base data from their callers: `src/devops_cli/roadmap/stage/stage_request.py:65:def gate_arguments` and `src/devops_cli/roadmap/plan_read.py:734:def specs_at`.
- The failing case of the issue is the plan of PR #3400: its scenario names only a field, and its task tests another rule. The test of the branch builds that plan and the refusal.

## Existing Tool Considered

No open, maintained tool covers this repository-specific plan rule. The change extends `check_proposal` and its base-spec reader, adopts no new dependency, and builds about 150 lines with about 200 lines of tests.

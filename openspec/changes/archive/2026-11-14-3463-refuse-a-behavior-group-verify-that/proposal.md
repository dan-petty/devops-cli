# Proposal: #3463

## Why

The stage form check accepts a `behavior` group whose `verify` command runs no test. `_behavior_problems` requires a `test` and a `verify`, and `form_problems` judges the form of the command (#3427), but no rule reads the command's target. A behavior group with `uv run devops ci docs` or `uv run devops ci test tests/roadmap/` passes, and the step proves nothing about the behavior that the group changes. The prompt at `src/devops_cli/ai/tasks/roadmap_stage_change.md` already says that a behavior group's `verify` runs its test; no check enforces it. Closes #3463.

## What Changes

- `form_problems` refuses a `behavior` group whose `verify` command names no test module of the group, or names a test module that `test`, `changes`, `creates` and `reads` do not name. A test directory is no test module. A negative search stays accepted, and a command with a form problem gets only the form problem.
- The problem names the group, the command and the test module that the group should run.
- The stage prompt needs no change: it states the rule.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/tests-gate`: A behavior group runs a test module of the group.

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_form.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_form.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`

## Feasibility

Read on 2026-11-14 against `origin/main` at `04107728d`.

- The check that accepts the group: `src/devops_cli/roadmap/stage/stage_form.py:247:def form_problems`, and `src/devops_cli/roadmap/stage/stage_change.py:585:def _behavior_problems` requires only the presence of `test` and `verify`.
- The gap reproduces on the sample group of `tests/support/builders.py`: `form_problems([group with verify="uv run devops ci docs"])` returns `[]`, and so does `uv run devops ci test tests/roadmap/`.
- The prompt states the rule: `src/devops_cli/ai/tasks/roadmap_stage_change.md:18`, a `behavior` group's `verify` runs its test.
- The test-module test lives in the same module: `src/devops_cli/roadmap/stage/stage_form.py:147:def _is_test_module`.

## Existing Tool Considered

No open, maintained tool checks the verify of a repository-specific plan. The rule extends `form_problems`, which already parses each command with `shlex.split`. The cost is about 2,000 tokens to build and test, and about 40 lines of code.

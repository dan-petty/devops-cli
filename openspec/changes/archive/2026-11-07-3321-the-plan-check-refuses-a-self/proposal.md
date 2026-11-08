# Proposal

## Why

The plan check accepts three defects that a reviewer finds by reading (#3321). A task group can name a path under the plan's own change folder, so the plan lists itself as work. A spec scenario can name a function or a file with no behavior test, so no test begins the work. A quoted search can list a file that no task or design decision covers, so a later change misses it. The plan of PR #3278 held all three and passed the check.

## What Changes

- Add the `change` key to `check_proposal`: the name of the plan's own change folder.
- Refuse a group `changes` path or a task code span under `openspec/changes/<change>/`.
- Refuse a spec scenario that names a function or a file when no `behavior` group's `test` or `verify` names it and the scenario names no command.
- Require each file of a quoted `References to` answer outside `openspec/changes/archive/` to appear in a group `changes` or a design decision.
- Add the problem texts to `MESSAGES.roadmap` and the rules to the planner prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- Add the plan of PR #3278 to the golden set, with a defect for each new rule.
- State the score of the chosen model before and after the change in `docs/ROADMAP_WORKFLOW.md`.
- The change carries a spec delta because `check_proposal` decides whether the stage job accepts a plan, and a consumer observes that answer.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: The plan check refuses a path of the plan's own change folder, a scenario that names code with no behavior test, and a file from a quoted search that no task or design decision covers.

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/stage/stage_paths.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_eval_gates.py`, `src/devops_cli/lang/en/messages.py`
- Prompts: `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- Documents: `docs/ROADMAP_WORKFLOW.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_own_change.py`, `tests/roadmap/stage/test_roadmap_stage_scenario_evidence.py`, `tests/roadmap/stage/test_roadmap_stage_reference_coverage.py`, `tests/fixtures/roadmap_eval/stage/3278-a-plan-that-names-its-own`

## Feasibility

- `check_proposal` in `src/devops_cli/roadmap/stage/stage_change.py` calls `_delta_problems`, `content_problems`, `form_problems`, `path_problems` and `criterion_problems`. It has no parameter for the own change folder, and the stage job holds that name in `StageTarget.change` (`src/devops_cli/roadmap/stage/stage.py:231`).
- `path_problems` in `src/devops_cli/roadmap/stage/stage_paths.py` reads `reads`, `changes`, the code spans of each task and `verify`. `code_spans` is in `src/devops_cli/roadmap/step_files.py`, so the own-change scan reuses it for a task.
- `reference_answer` in `src/devops_cli/roadmap/stage/stage_references.py` writes `References to '<name>': files N, lines M.` and one `<path>: <count> (line <n>)` line for each file that it keeps. The stage prompt tells the model to quote the tool answer in `feasibility`.
- `StageProposal.decisions` and `StageProposal.rejected` render to `design.md`, so a design decision that leaves a file unchanged is a text that the check reads.
- `StageCase.change` in `src/devops_cli/roadmap/stage/stage_eval_cases.py` holds the change folder of a recorded plan, and `PlanUnderTest.of_case` can pass it to `check_proposal`.
- `tests/roadmap/stage/test_roadmap_stage_paths.py` covers the group paths of `path_problems`, and `tests/roadmap/stage/test_roadmap_stage_content.py` covers the content gate. The new tests follow their form.
- First check against the real system: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_own_change.py` fails on the base because the module does not exist.
- Second check: `uv run devops openspec check` accepts the change folder after the delta is written.
- Third check: `uv run devops roadmap eval stage --dry-run` lists the new replay case with no model call.

## Existing Tool Considered

No open, maintained tool or library covers a check of a plan of this repository. Pydantic validates the schema of the reply, not a path against the plan's own change folder or a file against a quoted tool answer. The change adds to `check_proposal`, `path_problems` and `MESSAGES.roadmap`. To build it costs about 60k tokens, about 6k tokens a month to keep and fix, and about 3 hours of elapsed time. The change deletes no internal code.

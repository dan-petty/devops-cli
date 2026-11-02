# Proposal

## Why

#3057: an implement agent that finds a wrong path or a wrong premise in a plan can only stop, so a plan that is wrong but fixable blocks the item. The issue asks for a bounded amendment that the step applies in the same pull request.

## What Changes

- Add `src/devops_cli/roadmap/implement_amend.py`: classify a defect as a bounded amendment, a premise failure or a scope change, and carry the defect, the evidence and the corrected text.
- Let a step raise a bounded amendment in `implement_step.py` and apply it to `tasks.md` and the change folder before the exit checks.
- Record each applied amendment in the change folder's `tasks.md` and post it with its evidence on the pull request.
- Return the item to New with the evidence and no code on a false premise, and post a question on the issue on a scope change.
- Re-split a group that exceeds its token budget through the split step of `stage.py` and continue with the new groups.
- Add tests for the classifier, the tasks.md record, the pull request comment, the return and the re-split.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-step`: A step applies a bounded plan amendment, The amendment is recorded in tasks.md, The amendment is posted on the pull request, A false premise returns the item, A scope change waits for a person, An over-budget group is re-split

## Impact

- Code: `src/devops_cli/roadmap/implement_amend.py`, `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_submit.py`
- Documents: `openspec/changes/3057-plan-amendment/specs/roadmap-implement-step/spec.md`, `openspec/changes/3057-plan-amendment/tasks.md`
- Tests: `tests/roadmap/test_roadmap_implement_amend.py`, `tests/roadmap/test_roadmap_implement_step.py`

## Feasibility

- `read_file src/devops_cli/roadmap/implement_step.py` showed a step builds fixed inputs, runs one agent turn, and judges the exit; it has no path to change the plan (`StepInputs`, `run_step`).
- `file_symbols src/devops_cli/roadmap/stage.py` showed the existing split step: `_Planner._fit` asks the model with `StageSplit` and `_SPLIT_TASK`, and `_stop_on_budget` records an over-budget item.
- `read_spec roadmap-implement-step` lists the existing requirements that a step refuses an input over the window and writes nothing to GitHub, so the amendment needs both a new record and the pull request comment path.
- First checks of the implementation against the real system: `uv run devops roadmap implement --dry-run --item 3057 --group 1` builds the step inputs without a request, and `uv run devops ci test tests/roadmap/test_roadmap_implement_step.py` runs the step tests.

## Existing Tool Considered

No open, maintained tool or library covers a plan-amendment step inside the roadmap implement job. The project builds its own code. The cost is the tokens to build, keep and fix the classifier, the tasks.md record, the pull request comment, the return and the re-split, and the elapsed time to integrate it into the existing implement job.

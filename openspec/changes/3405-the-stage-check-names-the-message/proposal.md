# Proposal

## Why

A plan can name a `MESSAGES.roadmap` message in a task text and change no file that defines it, and the stage check accepts it (#3405). The verification pass sees the defect but does not return the plan to the planner, so a person has to edit the plan by hand.

## What Changes

- `content_problems` in `src/devops_cli/roadmap/stage_change.py` returns a problem that names `src/devops_cli/lang/en/messages.py` when a rendered task text names `MESSAGES.roadmap` and no group lists that file.
- The check matches the bare `MESSAGES.roadmap` group and a dotted attribute after it, across the task texts that render into `tasks.md`.
- The problem text is a new `stage_problem_*` entry in `src/devops_cli/lang/en/messages.py`, so no output string is hard-coded.
- `src/devops_cli/ai/tasks/roadmap_stage_verify.md` widens the `missing_path` type to a code change that needs a file that the plan does not change, and `tests/roadmap/test_roadmap_stage_verify.py` asserts the prompt says so.
- `tests/roadmap/test_roadmap_stage_plan.py` holds one case for a plan that names a message without the file and one for a plan that names it with the file.
- The change carries a spec delta: `content_problems` and the verification prompt are behavior that a consumer of the stage job observes.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: The stage check names the message file a task needs, The verification prompt names the missing path of a needed file

## Impact

- Code: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_verify.md`
- Tests: `tests/roadmap/test_roadmap_stage_plan.py`, `tests/roadmap/test_roadmap_stage_verify.py`

## Feasibility

- The probe `content_problems` is defined at src/devops_cli/roadmap/stage_change.py:576:def content_problems(proposal: StageProposal, probes: Sequence[str] = ()) -> list[str]: confirms the function that the issue extends, at the path the issue cites.
- The probe `The path src/devops_cli/roadmap/stage_change.py is a file of the staging commit.` confirms the check module.
- The probe `The path src/devops_cli/lang/en/messages.py is a file of the staging commit.` confirms the file that holds the `RoadmapMessages` catalog and the `MESSAGES.roadmap` entry.
- The probe `The path src/devops_cli/ai/tasks/roadmap_stage_verify.md is a file of the staging commit.` confirms the verification prompt.
- The probe `The path tests/roadmap/test_roadmap_stage_plan.py is a file of the staging commit.` confirms the test module beside the existing stage plan tests.
- The probe `The path tests/roadmap/test_roadmap_stage_verify.py is a file of the staging commit.` confirms the test module that reads the verification prompt.
- The probe `The path MESSAGES.roadmap is no file of the staging commit. No commit in the history deleted or renamed it.` shows that the name is a catalog attribute and not a path, so the check reads it in prose and names `src/devops_cli/lang/en/messages.py` as the file.
- First check: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` runs the new stage plan cases against the real code.
- Second check: `uv run devops ci test tests/roadmap/test_roadmap_stage_content.py` runs the existing content problems cases, which the change must keep passing.
- Third check: `uv run devops ci test tests/roadmap/test_roadmap_stage_verify.py` runs the prompt case.
- Fourth check: `uv run devops openspec check` validates the change folder.

## Existing Tool Considered

No open, maintained tool resolves a message name in the prose of a plan to the file that defines it, and the stage check already reads the task texts, so the change extends `content_problems` in `src/devops_cli/roadmap/stage_change.py`. It deletes no internal code.

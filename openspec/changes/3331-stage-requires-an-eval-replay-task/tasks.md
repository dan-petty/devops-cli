# Tasks

## 1. Refuse a plan that changes a stage trigger path without the eval replay task

Reads: `src/devops_cli/roadmap/stage_change.py`, `tests/roadmap/test_roadmap_stage_form.py`, `docs/ROADMAP_WORKFLOW.md`. Changes: `src/devops_cli/roadmap/stage_change.py`, `tests/roadmap/test_roadmap_stage_form.py`.

- [ ] 1.1 Add tests to `tests/roadmap/test_roadmap_stage_form.py` that call `check_proposal` on a plan whose one group changes `src/devops_cli/ai/tasks/roadmap_stage_change.md` with no replay task, with the replay command and no score, with the replay command and the before and after score, and on a plan that changes only `src/devops_cli/roadmap/stage.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_form.py` fails on the base
- [ ] 1.2 Add a rule to `check_proposal` in `src/devops_cli/roadmap/stage_change.py`. It reads the changed paths of every group. When a group changes `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/roadmap/stage_change.py` or `src/devops_cli/roadmap/stage_eval_gates.py`, it looks for one group task that holds `uv run devops roadmap eval stage --replay`, `score`, `before` and `after` in its title, test, implementation, documentation or verify. With no such task it returns one problem that names the changed path and the replay command. When the command is there and a score word is missing, it returns one problem that asks for the before and after score. A plan that changes no trigger path adds no problem
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_form.py` passes

## 2. Name the trigger paths and the replay task in the workflow document

Reads: `docs/ROADMAP_WORKFLOW.md`, `src/devops_cli/roadmap/stage_change.py`. Changes: `docs/ROADMAP_WORKFLOW.md`.

- [ ] 2.1 In `docs/ROADMAP_WORKFLOW.md`, at the eval replay rule, name the three paths that trigger the check and the exact task text that satisfies it: `uv run devops roadmap eval stage --replay` with the before and after score. Say that the stage job refuses a plan that misses it, and that `check_proposal` holds the rule
  - Verification: `uv run devops ci docs` passes
- [ ] 2.2 docs/ROADMAP_WORKFLOW.md, and run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs` passes

## Criteria

- Group 1: A test asserts that a plan editing `roadmap_stage_change.md` without an evaluation task is refused.
- Group 1: A test asserts that a plan editing `roadmap_stage_change.md` that includes the model replay evaluation passes.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

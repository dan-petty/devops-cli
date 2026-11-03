# Tasks

## 1. Refuse a plan that changes a stage trigger path without the eval replay task

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_form.py`, `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/roadmap/stage_criteria.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_form.py`, `docs/ROADMAP_WORKFLOW.md`. Changes: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_form.py`.

- [ ] 1.1 Add tests to `tests/roadmap/test_roadmap_stage_form.py` that call `check_proposal` on a plan whose one group changes each trigger path with no replay task, with the replay command and no score, with the replay command and the before and after score, and on a plan that changes only `src/devops_cli/roadmap/stage.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_form.py` fails on the base
- [ ] 1.2 Add a rule to `check_proposal` in `src/devops_cli/roadmap/stage_change.py`, with its problem texts in `MESSAGES.roadmap` in `src/devops_cli/lang/en/messages.py`. It reads the changed paths of every group. When a group changes `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_form.py`, `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/roadmap/stage_criteria.py` or `src/devops_cli/roadmap/stage_eval_gates.py`, it looks for one group task that holds `uv run devops roadmap eval stage --replay` and the words `score`, `before` and `after` in its title, test, implementation, documentation or verify. With no such task it returns one problem that names the changed path and the replay command. When the command is there and a score word is missing, it returns one problem that asks for the before and after score. A plan that changes no trigger path adds no problem
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_form.py` passes

## 2. Replay a plan that changes a trigger path without the replay task

Reads: `src/devops_cli/roadmap/stage_eval_cases.py`, `src/devops_cli/roadmap/stage_eval_gates.py`, `tests/fixtures/roadmap_eval/stage/`. Changes: `tests/fixtures/roadmap_eval/stage/3331-a-plan-that-changes-a-check/` (new), `src/devops_cli/roadmap/stage_eval_cases.py`.

- [ ] 2.1 Add the recorded plan of a plan whose group changes `src/devops_cli/roadmap/stage_change.py` and whose tasks hold no replay command, with the defect of the new rule and the message that the gate must give
  - Verification: `uv run devops roadmap eval stage --dry-run` passes
- [ ] 2.2 Run `uv run devops roadmap eval stage --replay` on the whole set and record the caught defects and the counts of the `paths` gate before and after the change
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_gates.py` passes

## 3. Name the trigger paths and state the score of the stage gate

Reads: `docs/ROADMAP_WORKFLOW.md`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_eval_run.py`. Changes: `docs/ROADMAP_WORKFLOW.md`.

- [ ] 3.1 In `docs/ROADMAP_WORKFLOW.md`, at the eval replay rule, name the six trigger paths and the exact task text that satisfies it: `uv run devops roadmap eval stage --replay` with the score before and after. Say that the stage job refuses a plan that misses it, and that `check_proposal` holds the rule
  - Verification: `uv run devops ci docs` passes
- [ ] 3.2 Run `uv run devops roadmap eval stage --replay` on the base and on the branch, and state the caught defects, the score of the same model and the counts of the `paths` gate before and after the change
  - Verification: `uv run devops ci docs` passes
- [ ] 3.3 Regenerate the documentation with `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs` passes

## Criteria

- Group 1: A test asserts that a plan editing `roadmap_stage_change.md` without an evaluation task is refused.
- Group 1: A test asserts that a plan editing `roadmap_stage_change.md` that includes the model replay evaluation passes.

## Workflow follow-up

- Pending a person: run `uv run devops roadmap eval stage --model <model>` with one model on the base and on the branch, and state both scores and the model.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

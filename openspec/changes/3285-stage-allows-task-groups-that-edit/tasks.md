# Tasks

## 1. Refuse a change-folder path in a task group

Reads: `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/stage_change.py`, `tests/roadmap/test_roadmap_stage_kind.py`. Changes: `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/stage_change.py`, `tests/roadmap/test_roadmap_stage_kind.py`.

- [ ] 1.1 In `tests/roadmap/test_roadmap_stage_kind.py`, assert that `StageGroup` refuses a `changes` or a `creates` path under `openspec/changes/` with a message that names the path, and that it accepts the same path in `reads`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_kind.py` fails on the base
- [ ] 1.2 Add a `_change_folder_problems` helper and a model validator to `StageGroup` in `src/devops_cli/roadmap/stage_change.py`. The validator raises `MESSAGES.roadmap.stage_bad_change_path` for a `changes` or a `creates` path equal to `_CHANGES_DIRECTORY` or starting with `openspec/changes/`, and leaves `reads` alone. Add the message text to the roadmap texts that `MESSAGES` serves
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_kind.py` passes

## 2. Report a change-folder path in the path check

Reads: `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/roadmap/stage_change.py`, `tests/roadmap/test_roadmap_stage_paths.py`. Changes: `src/devops_cli/roadmap/stage_paths.py`, `tests/roadmap/test_roadmap_stage_paths.py`.

- [ ] 2.1 In `tests/roadmap/test_roadmap_stage_paths.py`, assert that `path_problems` reports a group built with `model_construct` that creates a path under `openspec/changes/`, and that a group that only reads such a path in a tree that holds it has no problem
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_paths.py` fails on the base
- [ ] 2.2 In `path_problems` of `src/devops_cli/roadmap/stage_paths.py`, report a `changes` or a `creates` path that is `openspec/changes` or starts with `openspec/changes/` with `MESSAGES.roadmap.stage_bad_change_path`, before the checks for a created or an existing path
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_paths.py` passes

## 3. State the path rule in the stage prompt

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`.

- [ ] 3.1 Add one bullet to the path rules of `src/devops_cli/ai/tasks/roadmap_stage_change.md` that says an implementation group must not change or create a path under `openspec/changes/`. Add the matching case to `tests/roadmap/test_roadmap_stage_prompt_rules.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

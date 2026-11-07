# Tasks

## 1. Read only the marked code spans

Kind: behavior. Reads: `src/devops_cli/roadmap/step_files.py`, `src/devops_cli/roadmap/implement_amend.py`, `src/devops_cli/lang/en/messages.py`. Changes: `tests/roadmap/test_roadmap_step_files.py` (new), `src/devops_cli/roadmap/step_files.py`, `src/devops_cli/roadmap/implement_amend.py`, `src/devops_cli/lang/en/messages.py`.

- [x] 1.1 In `tests/roadmap/test_roadmap_step_files.py`, test that a prose span beside a marked command gives only the command, that the mark is removed before the program is read, that a marked command of an unknown program is refused with its reason, that an unmarked line gives no command, that the stage templates write the mark, and that the docstring of `_task_of` states the rule
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_step_files.py` fails on the base
- [x] 1.2 In `_task_of`, read as commands only the code spans that start with `$ `, and write the mark in the three stage templates and in the task that the plan amendment adds
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_step_files.py` passes

## 2. Write the active plans, tests and documents with the mark

Reads: `openspec/config.yaml`, `docs/roadmap/plan-recheck.md`. Changes: `openspec/config.yaml`, `docs/roadmap/plan-recheck.md`, the `tasks.md` files of the active changes, `tests/invariants/test_change_folders.py`, `tests/roadmap/test_roadmap_plan_rewrite.py`.

- [x] 2.1 Add the mark to each `Verification:` command of the active plans, the test fixtures and the snapshots, and name the mark in the plan rule of `openspec/config.yaml` and in `docs/roadmap/plan-recheck.md`
  - Verification: `$ uv run devops ci test tests/invariants/test_change_folders.py` passes

## 3. Archive the change

Reads: nothing. Changes: `openspec/changes/3596-read-only-the-marked-code-spans` (moved by the archive command).

- [ ] 3.1 Archive the change
  - Verification: `$ uv run devops openspec check`

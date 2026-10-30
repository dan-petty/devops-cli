# Tasks

## 1. The one restore

- [x] Write failing tests in `tests/test_roadmap_implement_step_ticks.py` and `tests/test_roadmap_implement_step_own_text.py`. Each test below ends done with the base text of `tasks.md` and the ticks of the own group, and a test names its stop reason where it stops. The cases: ticks of groups 1 and 2 with the number "2.1" deleted from a task of group 2; an edit of a command, a bullet or a line of a later group; an added group; a removed group; two tasks of a later group swapped; a section outside every group; a rewrite of the own text in the first turn and in the extra turn; a command that is rewritten to pass, where the original command runs and fails; a group ticked in part; an own group with an added task; a removed file and a file that is not UTF-8; CRLF and lone CR files; a tick with trailing spaces prints no line; a fix step that ticks or edits a task ends done with the text as it was; the note names the change.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step_ticks.py tests/test_roadmap_implement_step_own_text.py`
- [x] Replace the stops of `tasks.md` in `src/devops_cli/roadmap/implement_step.py` with one restore: `StepInputs` holds the raw text of the file before the run, the step writes that text with the ticks of the own group, and `_exit_failure` calls it where `_tasks_failure` was. Delete `_tasks_failure`, `_whole`, `_shape`, `_same_tasks`, `_restored_wrong`, `_restore_ticks`, `_restore_own_text`, `_own_group_failure`, `_other_groups_failure`, `_fix_tasks_failure`, `_region_bounds`, `TaskGroup.first_line`, `StepInputs.region` and `StepInputs.groups`. Delete the five messages that only the stops used and add the one for the note in `src/devops_cli/lang/en/messages.py`. Change the help of `devops roadmap implement` in `src/devops_cli/lang/en/help.py`.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step_ticks.py tests/test_roadmap_implement_step_own_text.py tests/test_roadmap_implement_step.py tests/test_roadmap_implement_job.py`
- [x] Rewrite the tests in `tests/test_roadmap_implement_step.py` that expect a stop for an edit of `tasks.md`, and delete the tests whose stop is gone.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step.py`

## 2. The prompt

- [x] Write a failing test in `tests/test_roadmap_implement_step_own_text.py`: the instructions say that the job writes the whole file back and keeps only the ticks of the group.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step_own_text.py`
- [x] Change `src/devops_cli/ai/tasks/roadmap_implement_step.md`.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step_own_text.py tests/test_ai_task_implement.py`

## 3. The documentation

- [ ] Regenerate the documentation with `devops docs generate --sync-readme`.
  - Verification: `uv run devops docs check`

## 4. Archive

- [ ] Archive the change.
  - Verification: `uv run devops openspec archive 2790-tasks-md-job-owned`

# Tasks

## 1. The restore of the own group

- [x] Write failing tests in `tests/test_roadmap_implement_step_own_text.py`: a step that rewrites the text of a task of its group and ticks it ends done, and the commit holds the text from before the run with the tick kept; a rewrite in the extra turn for the ticks is restored; a rewrite of a `Verification:` line to a command that passes does not run, and the original command that fails is named in the stop; an added, removed or reordered task and a changed heading still stop the step; a rewrite of a line of the group that is no task is restored; a file with CRLF line ends keeps them; the step prints one line that names the group, and none for a tick only; a fix step that edits a task still stops.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step_own_text.py`
- [x] Add the fields `first_line` and `end_line` to `TaskGroup` in `src/devops_cli/roadmap/implement_step.py`, left out of its comparison. Stop on a change of the number, the order or the heading of the tasks of the own group. Write the text of the group from before the run back, keep the checkboxes of the agent with the code that restores ticks, check the write by parsing the file again, and print one line from `src/devops_cli/lang/en/messages.py`.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step_own_text.py tests/test_roadmap_implement_step_ticks.py tests/test_roadmap_implement_step.py tests/test_roadmap_implement_job.py`

## 2. The prompt

- [x] Write a failing test in `tests/test_roadmap_implement_step_own_text.py`: the instructions of the step say not to edit the text of a task, and what to do when the path of a task is wrong.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step_own_text.py`
- [x] Add the sentences to `src/devops_cli/ai/tasks/roadmap_implement_step.md`.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step_own_text.py tests/test_ai_task_implement.py`

## 3. The documentation

- [x] Regenerate the documentation with `devops docs generate --sync-readme`.
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 4. Archive

- [x] Archive the change.
  - Verification: `uv run devops openspec archive 2774-own-task-text`

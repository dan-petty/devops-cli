# Tasks

## 1. The format run

- [x] Write failing tests in `tests/test_roadmap_implement_step_format.py`: unformatted correct code ends done with the formatted file in the commit and one line that names it; a formatted file prints no line; the format command names only the changed Python files; a lint error after the format run still stops the step; a format command that exits 2 stops the step with its output; a format command that runs out of time stops the step; the format run is the first command. Change the list of commands in `tests/test_roadmap_implement_step.py`.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step_format.py`
- [x] In `src/devops_cli/roadmap/implement_step.py`, add the format run to `_exit_failure`: run `uv run ruff format` on the changed Python files with `_command_failure`, stage the files that `git diff --name-only -z` lists, and print one line from `src/devops_cli/lang/en/messages.py`. Remove the `ruff format --check` row from `_static_failure`.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step_format.py tests/test_roadmap_implement_step.py tests/test_roadmap_implement_step_ticks.py tests/test_roadmap_implement_step_own_text.py tests/test_roadmap_implement_job.py`

## 2. The prompt

- [x] Write a failing test in `tests/test_roadmap_implement_step_format.py`: the instructions of the step say that the job formats the changed Python files.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step_format.py`
- [x] Add the sentence to `src/devops_cli/ai/tasks/roadmap_implement_step.md`.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step_format.py tests/test_ai_task_implement.py`

## 3. Safe tool arguments

- [x] Write failing tests in `tests/test_roadmap_implement_step_format.py`: the file names follow `--` for the format run, `ruff check` and `mypy --strict`, also for a name that starts with `-`; a changed Python file that is a link stops the step, and the target of the link stays as it was.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step_format.py`
- [x] In `src/devops_cli/roadmap/implement_step.py`, put `--` before the file names, and stop on a link before the format run, with a message from `src/devops_cli/lang/en/messages.py`.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step_format.py tests/test_roadmap_implement_step.py tests/test_roadmap_implement_step_own_text.py`

## 4. The documentation

- [x] Regenerate the documentation with `devops docs generate --sync-readme`.
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 5. Archive

- [x] Archive the change.
  - Verification: `uv run devops openspec archive 2789-job-formats-changed-files`

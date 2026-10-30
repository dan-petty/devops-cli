# Tasks

## 1. The tick turn

- [x] Write failing tests in `tests/test_roadmap_implement_step.py` and `tests/support/implement_step.py`: a step whose verification passes and whose agent forgot the ticks gets one extra turn, ends done, and changes only `tasks.md` in that turn; a turn that changes another file stops the step; a turn that leaves a task unticked stops the step; a failed verification runs no turn; the two turns share one budget; the spend counts both turns.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step.py`
- [x] Change `src/devops_cli/roadmap/implement_step.py` and `src/devops_cli/lang/en/messages.py`: run the ticks check last, run the extra turn on the same conversation, check with git that the turn changed only `tasks.md`, and count the spend of both turns.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step.py`

## 2. The instructions and the inputs

- [x] Write a failing test in `tests/test_roadmap_implement_step.py`: the user message of a step holds the path of the `tasks.md` of the change, and the message of a fix step does not.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step.py`
- [x] Add the section of the tasks file to the inputs, and word the instructions in `src/devops_cli/ai/tasks/roadmap_implement_step.md`. Update the snapshot of the inputs.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step.py tests/test_ai_task_implement.py`

## 3. The diff of a stopped step

- [x] Write failing tests in `tests/test_roadmap_implement_step.py` and `tests/test_roadmap_implement_job.py`: a stopped step reports the masked diff cut to a constant size; the stop comment holds the diff in a fenced block; a diff with a secret-looking string and a line of three backticks gives a comment with no secret and one fenced block that holds the whole diff.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step.py tests/test_roadmap_implement_job.py`
- [x] Add `CONST_ROADMAP_IMPLEMENT_DIFF_CHARS`, the fields `diff` and `diff_cut` of `StepOutcome`, the read of the diff in `implement_step.py`, and the fenced block in the stop comment of `implement_run.py` with its message.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step.py tests/test_roadmap_implement_job.py`

## 4. The documentation

- [x] Regenerate the documentation, the help of `devops roadmap implement` and the term in `CONTEXT.md`.
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 5. Archive

- [ ] Archive the change.
  - Verification: `uv run devops openspec archive 2721-implement-tick-turn`

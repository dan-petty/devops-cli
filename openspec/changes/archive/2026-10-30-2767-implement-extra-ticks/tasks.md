# Tasks

## 1. The restore of the other groups

- [x] Write failing tests in `tests/test_roadmap_implement_step_ticks.py`, `tests/test_roadmap_implement_step.py` and `tests/support/implement_step.py`: a step that ticks its group and a later group ends done, and the commit holds the later group unticked; a step that unticks an earlier group is restored; the extra turn that ticks a later group is restored; a text edit of another group, in the first turn and in the extra turn, still stops the step with the group named; a file with CRLF line ends keeps them; the step prints one line that names the restored groups; a fix step that ticks a task still stops.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step_ticks.py tests/test_roadmap_implement_step.py`
- [x] Add the field `line` to `GroupTask` in `src/devops_cli/roadmap/implement_step.py`, left out of its comparison. Compare the shape of every other group, restore the checkboxes of a group that differs only in them, check the restore by parsing the file again, and print one line from `src/devops_cli/lang/en/messages.py`.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step_ticks.py tests/test_roadmap_implement_step.py tests/test_roadmap_implement_job.py`

## 2. The prompt

- [x] Write a failing test in `tests/test_roadmap_implement_step_ticks.py`: the instructions of the step say to tick only the tasks of the group, and give the reason.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step_ticks.py`
- [x] Add the sentence to `src/devops_cli/ai/tasks/roadmap_implement_step.md`.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step_ticks.py tests/test_ai_task_implement.py`

## 3. The documentation

- [x] Regenerate the documentation with `devops docs generate --sync-readme`.
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 4. Review fixes

- [x] Write failing tests in `tests/test_roadmap_implement_step_ticks.py`: a changed bullet and an added line in a later group stop the step; a file with many lone CR line ends is restored on the right line; a copy of a group that hides an edit stops a step and a fix step; a base file with a group number twice is refused.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step_ticks.py`
- [x] Compare the whole text of each other group after the restore, split the file as the parser does, refuse a group number that two groups hold, and name the stale sentence in the help text, the specs and the proposal.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step_ticks.py tests/test_roadmap_implement_step.py`

## 5. Archive

- [x] Archive the change.
  - Verification: `uv run devops openspec archive 2767-implement-extra-ticks`

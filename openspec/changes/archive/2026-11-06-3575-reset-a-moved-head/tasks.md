## 1. Reset a moved head

Reads: `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_wip.py`. Changes: `tests/roadmap/test_roadmap_implement_step.py`, `tests/roadmap/test_roadmap_implement_step_failure_class.py`, `tests/roadmap/test_roadmap_implement_step_repair.py`, `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/lang/en/messages.py`.

- [x] 1.1 Replace the tests that held the stop of a moved head with tests on a real git repository: a commit of the agent in a turn and in an extra turn is reset and the step ends done with one commit; the reset line is printed once; a failed check after the reset stops with that failure and the `wip:` commit stays; a failed `git reset --soft` stops with `head_moved` and names the command and the output of git
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step.py tests/roadmap/test_roadmap_implement_step_failure_class.py tests/roadmap/test_roadmap_implement_step_repair.py`
- [x] 1.2 In `_exit_failure`, reset a head that is not the expected head of the keeper with `git reset --soft`, print the muted line, and stop with `head_moved` only when the reset fails
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step.py tests/roadmap/test_roadmap_implement_step_failure_class.py tests/roadmap/test_roadmap_implement_step_repair.py`

## 2. Tell the reader

Reads: `docs/ROADMAP_WORKFLOW.md`. Changes: `docs/ROADMAP_WORKFLOW.md`.

- [x] 2.1 In `docs/ROADMAP_WORKFLOW.md`, state the reset of a moved head and the new meaning of the class `head_moved`
  - Verification: `uv run devops docs check`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

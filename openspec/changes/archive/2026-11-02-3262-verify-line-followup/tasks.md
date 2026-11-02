# Tasks

## 1. A text of a group stays on one line

Kind: behavior. Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_form.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_form.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_task_verification.py`.

- [x] 1.1 In `tests/roadmap/test_roadmap_stage_task_verification.py`, add a round trip with a line break and a second `Verification:` line in each text of a group and in the reason of a criterion, the refusal of a backtick in `verify`, and the check of the shell policy on each command of the golden set
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_task_verification.py` fails on the base: 9 tests fail
- [x] 1.2 In `src/devops_cli/roadmap/stage_change.py`, fold `Text` and `Sentence` to one line and fold the reason of a criterion when it is written. In `src/devops_cli/roadmap/stage_form.py` and `src/devops_cli/lang/en/messages.py`, refuse a backtick in `verify`
  - Verification: `uv run devops ci test tests/roadmap` passes

## 2. The rule for tasks names the Verification line

Kind: other. Reads: `openspec/config.yaml`. Changes: `openspec/config.yaml`.

- [x] 2.1 In the rule for tasks of `openspec/config.yaml`, say that a verification command goes on a nested `Verification:` line, with the command in a code span
  - Verification: `uv run devops openspec check` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

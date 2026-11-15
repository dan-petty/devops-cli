# Tasks

## 1. The premise check before the first step

Kind: behavior. Reads: `src/devops_cli/roadmap/premise.py`. Changes: `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/implement/test_roadmap_implement_checkpoint.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`.

- [x] 1.1 Change the test `TestAGuardThatTheBranchTipDefines` so that a false premise of group 3 returns the item before the step of group 1, and add the test `TestAGuardOfAGroupThatPassed` for a group that passed in an earlier Job
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_checkpoint.py` fails on the base
- [x] 1.2 Call `_check_premise` once at the first group boundary for every open behavior group, and change the comment `implement_comment_premise_defined`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_checkpoint.py tests/roadmap/implement/test_roadmap_implement_job.py`

## 2. The spend of a return

Kind: behavior. Reads: `src/devops_cli/roadmap/job_result.py`. Changes: `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/implement/implement_submit.py`, `tests/roadmap/implement/test_roadmap_implement_phase_marks.py`, `tests/roadmap/implement/test_roadmap_implement_job_result.py`.

- [x] 2.1 Change the tests of `test_roadmap_implement_phase_marks.py` so that a return keeps `implement.spend` and its count, and add the test that the report of a returned Job logs its tokens and clears the spend
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job_result.py` fails on the base
- [x] 2.2 Keep the spend in `_return_to_new`, and clear the spend and its count in `_report` for a returned Job
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job_result.py tests/roadmap/implement/test_roadmap_implement_phase_marks.py`

## 3. Documents

Kind: other. Changes: `docs/roadmap/implement.md`, `src/devops_cli/roadmap/stores/store.py`.

- [x] 3.1 Describe the time of the premise check and the spend of a return in `docs/roadmap/implement.md` and in the docstring of `ImplementRecordKey`
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- The prose rule of `added_guard` stays. #3453 replaces it with an `Adds:` line.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

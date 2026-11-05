# Tasks

## 1. Refuse a behavior group whose test passes on base

Reads: `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/ci/fail_to_pass.py`, `src/devops_cli/roadmap/step_files.py`. Changes: `src/devops_cli/roadmap/implement_base_replay.py` (new), `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/step_files.py`, `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/ci/fail_to_pass.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_implement_step_fail_to_pass.py` (new).

- [x] 1.1 Write `tests/roadmap/test_roadmap_implement_step_fail_to_pass.py` with cases for a test that passes on base, a collection error on base, a test that fails on base and passes after, and a behavior group that changes no test file
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step_fail_to_pass.py` fails on the base
- [x] 1.2 Write `src/devops_cli/roadmap/implement_base_replay.py`, make `is_test_file` public in `src/devops_cli/ci/fail_to_pass.py`, add `is_behavior` to the task group of `src/devops_cli/roadmap/step_files.py`, and check the tests of a behavior group on base in `_exit_failure` of `src/devops_cli/roadmap/implement_step.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step_fail_to_pass.py` passes

## 2. Record the replay in the trace and the PR comment

Reads: `src/devops_cli/roadmap/implement_trace.py`, `src/devops_cli/roadmap/implement_run.py`. Changes: `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_tool_log.py`, `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_implement_step_trace.py`, `tests/roadmap/test_roadmap_implement_job.py`.

- [x] 2.1 Write a case in `tests/roadmap/test_roadmap_implement_step_trace.py` for a base run as a check event, and a case in `tests/roadmap/test_roadmap_implement_job.py` for the fail-to-pass line of each behavior group in the PR comment
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step_trace.py tests/roadmap/test_roadmap_implement_job.py` fails on the base
- [x] 2.2 Record the replay as a check event of the trace, add the replay to the step outcome, and add one fail-to-pass line for each behavior group to the PR comment
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step_trace.py tests/roadmap/test_roadmap_implement_job.py` passes

## 3. Record the output of a group of kind other

Reads: `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_run.py`. Changes: `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_implement_step_fail_to_pass.py`.

- [ ] 3.1 Write a case in `tests/roadmap/test_roadmap_implement_step_fail_to_pass.py` for a group of kind `other` whose verify command prints a line, and check that the step outcome holds the line
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step_fail_to_pass.py` fails on the base
- [ ] 3.2 Record the masked, bounded output of each verify command of a group of kind `other` in the step outcome, and print it in the PR comment
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step_fail_to_pass.py` passes

## 4. Document the check

Reads: `docs/roadmap/implement.md`. Changes: `docs/roadmap/implement.md`.

- [ ] 4.1 Add the fail-to-pass check of a behavior group to the exit checks of a step in `docs/roadmap/implement.md`, and state the PR comment line
  - Verification: `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

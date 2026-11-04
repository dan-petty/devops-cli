# Tasks

## 1. Refuse a verify command that runs a test the group does not name

Reads: `src/devops_cli/roadmap/stage_form.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/implement_shell_policy.py`, `tests/roadmap/test_roadmap_stage_form.py`. Changes: `src/devops_cli/roadmap/stage_form.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_form.py`.

- [ ] 1.1 Add `test_a_verify_command_that_runs_an_unnamed_test_module_is_refused` to `tests/roadmap/test_roadmap_stage_form.py`: a group that changes `src/devops_cli/ai/tasks/roadmap_stage_verify.md` and `tests/roadmap/test_roadmap_stage_verify.py` with `uv run devops ci test tests/roadmap/test_roadmap_stage_task_verification.py` gets one problem that names group 1, the command and the module
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_form.py` fails on the base
- [ ] 1.2 Add the message `stage_problem_verify_test` to `RoadmapMessages` in `src/devops_cli/lang/en/messages.py`, formatted with `group`, `command` and `path`. In `src/devops_cli/roadmap/stage_form.py`, add `_verify_test_problems(number, group)`: split the `verify` command into words, keep the words that `_is_test_module` accepts as `PurePosixPath`, and return one problem for each kept path that is in none of the group's `changes`, `creates` and `reads`. Call it from `form_problems` beside `_verify_problems`. Add cases for `reads`, `changes`, `creates`, two unnamed modules and a command with no test module
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_form.py` passes
- [ ] 1.3 Add the rule to the module docstring of `src/devops_cli/roadmap/stage_form.py`, and run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs` passes

## 2. Keep the staged plans of the samples inside the new rule

Reads: `tests/support/builders.py`, `tests/roadmap/test_roadmap_stage_task_verification.py`, `tests/roadmap/test_roadmap_stage_plan.py`. Changes: `tests/support/builders.py`, `tests/roadmap/test_roadmap_stage_plan.py`.

- [ ] 2.1 Run `uv run devops ci test tests/roadmap/test_roadmap_stage_task_verification.py` and read each group that `make_stage_proposal` in `tests/support/builders.py` gives. Where its `verify` command runs a test module that the group does not name, add that module to the group's `reads` and keep the command. Adjust the cases of `tests/roadmap/test_roadmap_stage_plan.py` the same way
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py tests/roadmap/test_roadmap_stage_task_verification.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

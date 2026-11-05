# Tasks

## 1. The reader reports each bad plan

Reads: `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/roadmap/implement_shell_policy.py`, `src/devops_cli/roadmap/step_files.py`, `tests/roadmap/test_roadmap_plan_read.py`. Changes: `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/lang/en/messages.py`, `docs/roadmap/plan-check.md`, `tests/roadmap/test_roadmap_plan_read.py`, `tests/roadmap/test_roadmap_plan_check.py`, `tests/commands/test_roadmap_plan_check_cmd.py`.

- [x] 1.1 Add failing tests: the reader raises only `PlanReadError` over each change folder of the tree, a group with no changed file and a group that changes a path of the change folder each give a `PlanReadError` for `tasks.md`, a refused span of a later task gives one, and plan-check reports each of the two groups as a `read` problem with exit code 1 and no trace
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_plan_read.py` fails on the base
- [x] 1.2 Turn the pydantic error of a group into a `PlanReadError` for `tasks.md` that names the group, and judge each code span of each `Verification:` line with `verification_problem`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_plan_read.py` passes
- [x] 1.3 List the read problems in `docs/roadmap/plan-check.md`
  - Verification: `uv run devops ci docs`

## 2. The validation drops only the skip_specs note

Reads: `src/devops_cli/roadmap/stage_validate.py`, `tests/roadmap/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/roadmap/stage_validate.py`, `tests/roadmap/test_roadmap_stage_plan.py`.

- [x] 2.1 Add failing tests: `validate_change` gives no problem for the `skip_specs` note, and gives a problem for another INFO issue next to it
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails on the base
- [x] 2.2 Drop the one `skip_specs` message from the issues of `validate_change`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes

## 3. The stage prompt names a sample file by a bare name

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`.

- [x] 3.1 Add a failing test that reads the stage prompt and asserts the bare-name rule for a sample file
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py` fails on the base
- [x] 3.2 Add the bare-name sentence to the stage prompt
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py` passes

## Workflow follow-up

- Sample paths in plans: #3492.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

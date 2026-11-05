# Tasks

## 1. Plan-check measures each task group

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_eval_run.py`, `src/devops_cli/roadmap/stage_verify_eval.py`, `src/devops_cli/roadmap/clone_git.py`, `tests/support/roadmap_stage.py`. Changes: `src/devops_cli/roadmap/plan_check.py`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/clone_git.py`, `src/devops_cli/roadmap/stage_eval_run.py`, `src/devops_cli/roadmap/stage_verify_eval.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`, `tests/roadmap/test_roadmap_plan_check.py`, `tests/roadmap/test_roadmap_stage_eval_run.py`, `docs/roadmap/plan-check.md`, `docs/commands/roadmap.md`, `docs/CLI_REFERENCE.md`, `README.md`.

- [x] 1.1 Add to `tests/roadmap/test_roadmap_plan_check.py` a test that the figure of `plan-check` for a group equals the figure that `measure_groups` gives the stage job for the same plan, a test that `plan-check` reports a group over the budget, a test that it reports no problem for a group under the budget, a test that it reports a group that changes a file that exists and packs no file, and a test that a group that only creates a file has no problem
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_plan_check.py` fails on the base
- [x] 1.2 Move `checkout_at` to `src/devops_cli/roadmap/clone_git.py` with an `operation` argument and update its two callers, add `files` to `MeasuredGroup` and add `shared_texts` to `src/devops_cli/roadmap/stage_change.py`, call `shared_texts` in `src/devops_cli/roadmap/stage.py`, measure each group in `src/devops_cli/roadmap/plan_check.py` on the head commit with the setting `roadmap.stage.step_tokens`, and add the messages `plan_check_group_over_budget` and `plan_check_group_no_files` to `src/devops_cli/lang/en/messages.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_plan_check.py tests/roadmap/test_roadmap_stage_eval_run.py tests/roadmap/test_roadmap_stage_measure.py` passes
- [x] 1.3 Edit `docs/roadmap/plan-check.md` to say that the command measures each group on the head commit with the budget of `roadmap.stage.step_tokens`, reports a group over it and a group that packs no file, and counts a created file as one line, edit the help text `plan_check` in `src/devops_cli/lang/en/help.py` to name the measure, and run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs` passes

## 2. The record keeps the size of the first request of each step

Reads: `src/devops_cli/roadmap/implement_trace.py`, `tests/support/roadmap_implement.py`, `tests/support/model_script.py`. Changes: `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_run.py`, `tests/roadmap/test_roadmap_implement_step_trace.py`, `tests/roadmap/test_roadmap_implement_job_trace.py`, `docs/ROADMAP_WORKFLOW.md`.

- [x] 2.1 Add to `tests/roadmap/test_roadmap_implement_step_trace.py` a test that the outcome of a step holds the input tokens of its first model request, and add to `tests/roadmap/test_roadmap_implement_job_trace.py` a test that `implement.spend` holds that figure for each step, and a test that a run with more events than the trace limit keeps the figure of each step while its trace has a `dropped` count above 0
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step_trace.py tests/roadmap/test_roadmap_implement_job_trace.py` fails on the base
- [x] 2.2 Add `first_request_tokens` to `_Run` and to `StepOutcome` in `src/devops_cli/roadmap/implement_step.py`, set it from the first reply of the first turn of the step, and write `steps` in `_spend` of `src/devops_cli/roadmap/implement_run.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step_trace.py tests/roadmap/test_roadmap_implement_job_trace.py` passes
- [x] 2.3 Edit `docs/ROADMAP_WORKFLOW.md` to say that `implement.spend` holds the input tokens of the first request of each step, apart from the trace
  - Verification: `uv run devops ci docs` passes

## Criteria

- Group 1: `plan-check` calls `measure_groups`. A test holds that the figure of `plan-check` equals the figure of the stage job for the same plan.
- Group 1: A test: `plan-check` prints each group over the budget.
- Group 1: A test: `plan-check` prints each group with 0 packed files.
- Group 2: A test: the run record of a fixture step holds the size of its first request.
- Group 2: A test: a fixture step with more events than the trace limit keeps the size of its first request, and its trace has a `dropped` count above 0.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

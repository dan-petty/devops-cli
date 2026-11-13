# Tasks

## 1. End an attempt at the time budget of the step

Kind: behavior. Reads: `src/devops_cli/roadmap/steps/fix_plan.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/service_stop.py`, `src/devops_cli/roadmap/failure.py`. Changes: `src/devops_cli/roadmap/steps/fix_plan.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/time_budget.py`, `src/devops_cli/roadmap/round_log.py`, `src/devops_cli/roadmap/job_result.py`, `src/devops_cli/exceptions/roadmap.py`, `src/devops_cli/exceptions/__init__.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/commands/roadmap_step_fix_plan.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/telemetry/instruments.py`, `tests/roadmap/steps/test_roadmap_fix_plan_budget.py`, `tests/commands/test_roadmap_step_fix_plan.py`, `tests/invariants/test_k8s_manifests.py`.

- [x] 1.1 Write `test_a_spent_budget_ends_the_attempt_with_a_timeout_comment_and_no_push`, `test_a_budget_that_ends_after_the_plan_run_pushes_no_revision` and `test_each_review_of_an_attempt_logs_one_progress_line` in `tests/roadmap/steps/test_roadmap_fix_plan_budget.py`, `test_confirm_writes_the_progress_and_the_result_lines_to_stderr` in `tests/commands/test_roadmap_step_fix_plan.py`, and `test_the_fix_plan_time_budget_ends_before_the_deadline_of_each_job_template` in `tests/invariants/test_k8s_manifests.py`
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [x] 1.2 Add the setting `roadmap.fix_plan.time_budget_seconds`, `TimeBudget` and `RoadmapTimeBudgetError`, which the step gives the class `timeout`; check the budget before each plan run and each review run of the planner; log the progress line of each review; end the attempt `timeout` with no push and a comment; write the lines of the step to stderr in the command
  - Verification: `$ uv run devops ci test tests/roadmap/steps tests/roadmap/stage tests/roadmap/test_job_result.py tests/commands/test_roadmap_step_fix_plan.py tests/invariants/test_k8s_manifests.py`

## 2. Document the budget and the result

Kind: other. Reads: `docs/roadmap/stage.md`, `docs/roadmap/job-success.md`. Changes: `docs/roadmap/stage.md`, `docs/roadmap/job-success.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/CLUSTER.md`, `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`, `docs/ERRORS.md`, `docs/TELEMETRY.md`.

- [x] 2.1 Write the budget, the result `timeout`, its comment and the progress line in the fix-plan step of `docs/roadmap/stage.md`, the `fix_plan` row of `docs/roadmap/job-success.md`, the `fix_plan.result` key, the stop sites and the class `timeout` of `docs/ROADMAP_WORKFLOW.md`, and item 23 of `docs/CLUSTER.md`, and regenerate the documents of the settings, the errors and the metrics
  - Verification: `$ uv run devops docs generate`

## Criteria

- Group 1: `uv run devops ci fail-to-pass --base origin/main` shows that each new test fails on the base and passes on the head.
- Group 2: `uv run devops docs generate` leaves no diff.
- Pending a person: after the release rolls the Service image, a fix-plan Job whose budget ends writes `roadmap job result: job=fix_plan ... result=timeout ... class=timeout` before its deadline, and Loki holds one `fix-plan progress:` line for each review of a fix-plan run.

## Workflow follow-up

- #5379 finds the call or the wait that did not end for 39 minutes in the attempt on #5350: the budget cannot stop such a call.

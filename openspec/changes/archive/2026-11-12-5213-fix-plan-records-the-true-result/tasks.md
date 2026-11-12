# Tasks

## 1. Record the true result of each attempt

Kind: behavior. Reads: `src/devops_cli/roadmap/steps/fix_plan.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/job_result.py`, `src/devops_cli/roadmap/planned.py`. Changes: `src/devops_cli/roadmap/steps/fix_plan.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/job_result.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/telemetry/instruments.py`, `tests/roadmap/steps/test_roadmap_fix_plan.py`, `tests/roadmap/steps/test_roadmap_fix_plan_comment.py`, `tests/roadmap/test_job_result.py`, `tests/commands/test_roadmap_step_fix_plan.py`, `tests/support/roadmap_fix_plan.py`.

- [x] 1.1 Write `test_an_unreadable_head_writes_no_result_line_and_uses_no_attempt`, `test_an_unreadable_head_waits_six_hours`, `test_a_failed_repair_keeps_the_findings_of_the_head_review`, `test_a_gate_failure_before_the_review_has_no_review_counts`, `test_a_stop_before_the_review_is_stopped_with_its_name`, `test_a_gated_plan_is_pushed_when_the_repair_fails`, `test_a_gated_plan_that_differs_is_pushed_after_a_clean_review`, `test_a_repair_that_returns_the_same_plan_is_unchanged`, `test_a_clean_head_with_listed_findings_is_dismissed`, `test_the_head_review_does_not_take_the_screen` and the replays of the heads of #4917, #4963 and #5032 in `tests/roadmap/steps/test_roadmap_fix_plan.py`, `test_fix_plan_counts_only_a_pushed_repair_as_success` in `tests/roadmap/test_job_result.py`, and the read of the head before the marks in `test_the_dry_run_makes_no_request_and_lists_the_reads_and_the_writes`, with the head of #4917 in `tests/fixtures/roadmap/plan_heads/4917-ba8cc66fd2f4/` and the stage comments of #4472, #2968 and #4697 in `tests/fixtures/roadmap_fix_plan/`
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [x] 1.2 Read the head before the marks and end a refused read `unreadable`; keep the gated plan, the step and the findings of the head review in `PlanRevision`; add `same_plan`, the screen flag of `_review` and the open plans of `revise_plan`; decide `stopped`, `failed`, `revised`, `cleared`, `regated`, `dismissed` and `unchanged` in that order; write the lines, the counts, the comments and the dry run
  - Verification: `$ uv run devops ci test tests/roadmap/steps tests/roadmap/stage tests/roadmap/test_job_result.py tests/commands/test_roadmap_step_fix_plan.py`

## 2. Document the results

Kind: other. Reads: `docs/roadmap/stage.md`, `docs/roadmap/job-success.md`. Changes: `docs/adr/0021-the-roadmap-service-is-a-webhook-router-cluster-pods-run-the-roadmap-jobs-and-valkey-holds-their-shared-state.md`, `docs/roadmap/job-success.md`, `docs/roadmap/stage.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/TELEMETRY.md`, `k8s/README.md`.

- [x] 2.1 Add a `Status History` line for the `fix-plan` row of section 8 to ADR 0021, and write the read before the marks, the results and their pushes, the counts and the comments in the `fix_plan` row of `docs/roadmap/job-success.md`, the fix-plan step of `docs/roadmap/stage.md`, the `fix_plan.*` keys and the class `premise_false` of `docs/ROADMAP_WORKFLOW.md`, and item 23 of `k8s/README.md`, and regenerate the documents of the messages and the metrics
  - Verification: `$ uv run devops docs generate`

## Criteria

- Group 1: `uv run devops ci fail-to-pass --base origin/main` shows that each new test fails on the base and passes on the head, except `test_an_unreadable_head_waits_six_hours`, `test_fix_plan_counts_only_a_pushed_repair_as_success` and the replays of #4963 and #5032, which pass on both.
- Group 1: `uv run pytest tests/roadmap/steps/test_roadmap_fix_plan.py -k replay` passes: the head of #4917 ends `regated` with a push, and the heads of #4963 and #5032 read and get a review.
- Group 2: `uv run devops docs generate` leaves no diff, and `uv run devops docs check` passes.
- Pending a person: A table in a comment of the pull request gives the result that the live attempts of #4917, #4963, #5053 and #4980 got and the result that this change gives them.

## Workflow follow-up

- #5214 charges a plan that the reader refuses to the stage job, and #5215 checks each finding of the head review on the revision.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

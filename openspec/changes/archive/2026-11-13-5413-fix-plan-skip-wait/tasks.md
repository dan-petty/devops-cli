# Tasks

## 1. A named run skips the wait

Kind: behavior. Reads: `src/devops_cli/roadmap/steps/fix_plan.py`, `src/devops_cli/commands/roadmap_step_fix_plan.py`. Changes: `src/devops_cli/roadmap/steps/fix_plan.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/commands/roadmap_step_fix_plan.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`, `tests/roadmap/steps/test_roadmap_fix_plan.py`, `tests/commands/test_roadmap_step_fix_plan.py`.

- [x] 1.1 Write `test_skip_wait_selects_a_named_plan_within_the_wait`, `test_skip_wait_keeps_the_attempt_cap`, `test_the_row_keeps_the_wait`, `test_skip_wait_takes_one_more_attempt_on_a_head_of_an_older_release` and `test_an_attempt_records_its_release` in `tests/roadmap/steps/test_roadmap_fix_plan.py`, and `test_skip_wait_needs_confirm_and_a_named_item` in `tests/commands/test_roadmap_step_fix_plan.py`
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [x] 1.2 Add `skip_wait` to `select_fix_plan` and `run_fix_plan`, `fix_plan.version` to the attempt marks, the rule of one more attempt on a head of an older release with its log line, and the option `--skip-wait`
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_fix_plan.py tests/commands/test_roadmap_step_fix_plan.py`

## 2. A killed attempt has a class

Kind: behavior. Reads: `src/devops_cli/roadmap/time_budget.py`, `src/devops_cli/roadmap/request_plan.py`. Changes: `src/devops_cli/roadmap/attempt_kill.py` (new), `src/devops_cli/roadmap/time_budget.py`, `src/devops_cli/roadmap/steps/fix_plan.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/commands/roadmap_step_fix_plan.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/telemetry/instruments.py`, `tests/roadmap/test_attempt_kill.py` (new), `tests/roadmap/steps/test_roadmap_fix_plan_budget.py`, `tests/commands/test_roadmap_step_fix_plan.py`.

- [x] 2.1 Write `test_sigterm_raises_attempt_killed_in_the_main_thread`, `test_a_second_sigterm_meets_the_default_action`, `test_sigterm_raises_sets_no_handler_in_another_thread`, `test_the_exit_status_of_each_class` and `test_the_budget_gives_the_class_of_a_kill` in `tests/roadmap/test_attempt_kill.py`; `test_a_kill_before_the_budget_is_evicted_and_does_not_count`, `test_a_kill_after_the_budget_is_a_deadline_and_counts`, `test_a_stop_of_the_service_during_the_attempt_is_evicted` and `test_a_unit_that_a_kill_always_ends_stops_at_the_cap` in `tests/roadmap/steps/test_roadmap_fix_plan_budget.py`; and `test_sigterm_during_the_attempt_exits_75_and_records_the_eviction` in `tests/commands/test_roadmap_step_fix_plan.py`
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [x] 2.2 Add `AttemptKill`, `AttemptKilled` and `sigterm_raises`, `TimeBudget.spent`, the kill marks, the line and the counter of a killed attempt, `fix_plan.evicted`, the write of the kill marks in the dry run, and the exit status of the command
  - Verification: `$ uv run devops ci test tests/roadmap/test_attempt_kill.py tests/roadmap/steps tests/commands/test_roadmap_step_fix_plan.py`

## 3. Document the option and the kill classes

Kind: other. Reads: `docs/roadmap/stage.md`. Changes: `docs/roadmap/stage.md`, `docs/roadmap/job-success.md`, `docs/CLUSTER.md`, `docs/ROADMAP_WORKFLOW.md`, the ADR 0021 status history, `docs/commands/roadmap.md`, `docs/TELEMETRY.md`.

- [x] 3.1 Write `--skip-wait`, the extra attempt, `fix_plan.version`, `fix_plan.evicted` and the kill classes in `docs/roadmap/stage.md`, the fix-plan row of `docs/roadmap/job-success.md`, the row `fix_plan` of `docs/CLUSTER.md` and the fix-plan keys of `docs/ROADMAP_WORKFLOW.md`, add a dated line to the status history of ADR 0021, and regenerate the documents of the commands and of the metrics
  - Verification: `$ uv run devops docs generate`

## Criteria

- Group 1: `uv run pytest tests/roadmap/steps/test_roadmap_fix_plan.py::test_skip_wait_selects_a_named_plan_within_the_wait` passes: the record holds `fix_plan.at` 1 h ago and 1 attempt on the head, and the step selects the plan.
- Group 1: `uv run pytest tests/roadmap/steps/test_roadmap_fix_plan.py::test_skip_wait_keeps_the_attempt_cap` passes: with 2 attempts on the head from the current release, the step leaves the item out.
- Group 1: `uv run pytest tests/roadmap/steps/test_roadmap_fix_plan.py::test_the_row_keeps_the_wait` passes.
- Group 1: `uv run pytest tests/roadmap/steps/test_roadmap_fix_plan.py::test_skip_wait_takes_one_more_attempt_on_a_head_of_an_older_release` passes: a named run with `--skip-wait` selects a head with 2 attempts from an older release or with no release, and refuses a head with 2 attempts from the current release.
- Group 2: `uv run pytest tests/roadmap/steps/test_roadmap_fix_plan_budget.py::test_a_unit_that_a_kill_always_ends_stops_at_the_cap` passes: 3 evicted attempts do not count, and the step then stops at the cap of 2 attempts.
- Groups 1 and 2: `uv run devops ci fail-to-pass --base origin/main` shows that the new tests fail on the base and pass on the head.
- Group 3: `uv run devops docs check` passes.
- Pending a person: after the release of the Service image and the runner image, a named run `devops roadmap step fix-plan --pull 5390 --skip-wait --confirm` on the plan of #5272 starts and writes its result line.

## Workflow follow-up

- #5412 starts fix-plan Jobs from the Service with `--pull` and no `--skip-wait`. It can give the Jobs a `podFailurePolicy` with `onExitCodes` 75 and the action `Ignore`, the retry owner of an evicted attempt.
- #5379 limits each agent run below the margin of the budget, so a deadline kill becomes rare.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

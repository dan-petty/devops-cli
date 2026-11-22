# Tasks

## 1. Measure the delivery body above Closes

Kind: behavior. Reads: `CONTRIBUTING.md`, `src/devops_cli/roadmap/steps/open.py`, `tests/roadmap/steps/test_roadmap_step_open.py`, `tests/ai/agent_audit/test_filing.py`, `tests/commands/test_pr_describe.py`, `tests/invariants/test_workflow_contracts.py`, `tests/lang/test_language_catalogs.py`, `tests/roadmap/implement/test_roadmap_implement_body_retry.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`, `tests/roadmap/refine/test_roadmap_refine_placeholder.py`, `tests/roadmap/stage/test_roadmap_stage_module_test_order.py`, `tests/roadmap/stage/test_roadmap_stage_title.py`, `tests/roadmap/test_roadmap_pull_form.py`, `tests/roadmap/test_roadmap_retitle.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`, `tests/roadmap/implement/test_roadmap_implement_project_steps.py`, `tests/roadmap/refine/test_roadmap_refine_tracker.py`, `tests/roadmap/stage/test_roadmap_stage_paths.py`, `tests/roadmap/stage/test_roadmap_stage_trace_subject.py`, `tests/roadmap/test_roadmap_retitle_type.py`. Changes: `src/devops_cli/roadmap/pull_form.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_pull_form.py`, `tests/roadmap/steps/test_roadmap_step_open.py`.
Adds: `measured_body_text`

- [x] 1.1 Write `test_a_body_over_the_limit_above_closes_is_refused` in `tests/roadmap/test_roadmap_pull_form.py` first: a text of 1,001 characters above `Closes`, then the `Closes` and `Change:` lines that add 120 characters, gives `form_body_long` with length 1001, and the text of the problem names `Closes`. Add `test_a_body_at_the_limit_above_closes_has_no_problem` with a text of 1,000 characters, which gets no problem. Both fail on the base, which reports the whole body
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_pull_form.py` fails on the base
- [x] 1.2 In `src/devops_cli/roadmap/pull_form.py` add `measured_body_text`, which returns the text above the first line that starts with `<line> #`, with its trailing blank lines removed, and the whole body when there is no such line. Give `_text_problems` a keyword `line` and measure `len(text.rstrip())` there; pass `line="Closes"` from `body_problems` and `line="Plans"` from `plan_body_problems`. Measure `measured_body_text(body, "Closes")` in `open_body_problems`. In `src/devops_cli/lang/en/messages.py` change `form_body_long` to "The text above `{line}` has {length} characters. The limit is {limit}. Shorten the text above `{line}`." and pass the line at each call. State in the docstrings of `body_problems`, `open_body_problems` and `_text_problems` that the limit measures the text above the trailer line, with its trailing blank lines removed. Update `test_a_body_over_the_limit_before_its_trailers_is_refused`, `test_a_plan_text_over_the_limit_is_refused_and_not_cut` and the test of `tests/roadmap/steps/test_roadmap_step_open.py` that asserts the old measure
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_pull_form.py` passes

## 2. Give the plan text the whole body limit

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, `tests/commands/test_pr_describe.py`, `tests/roadmap/implement/test_roadmap_implement_body_retry.py`, `tests/roadmap/steps/test_roadmap_step_open.py`, `tests/roadmap/test_roadmap_pull_form.py`, `tests/roadmap/test_roadmap_retitle.py`, `tests/ai/agent_audit/test_filing.py`, `tests/invariants/test_workflow_contracts.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`, `tests/roadmap/implement/test_roadmap_implement_project_steps.py`, `tests/roadmap/refine/test_roadmap_refine_placeholder.py`, `tests/roadmap/stage/test_roadmap_stage_title.py`, `tests/roadmap/test_roadmap_retitle_type.py`. Changes: `src/devops_cli/roadmap/pull_form.py`, `tests/roadmap/test_roadmap_pull_form.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`.

- [x] 2.1 Write `test_the_room_of_a_plan_text_is_the_body_limit` in `tests/roadmap/test_roadmap_pull_form.py` first, in place of `test_the_room_of_a_plan_text_is_the_text_that_the_plan_form_takes`: `plan_body_room(3215, PLAN_CHANGE)` is 1000, a text of 1,000 characters builds a plan body, and a text of 1,001 characters is refused. It fails on the base, which gives a room below the limit
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_pull_form.py` fails on the base
- [x] 2.2 Make `plan_body_room` in `src/devops_cli/roadmap/pull_form.py` return `BODY_MAX_CHARS`, and state in its docstring that the limit measures the text above the `Plans` line, which the `Plans` and `Change:` lines leave whole. Keep the `Plans` and `Change:` lines of `build_plan_body` built by `_plan_lines`, change the assertion of the replaced test to read the problem of the longer text, and update `_room` and assertions in `tests/roadmap/stage/test_roadmap_stage_plan.py` to measure the text above `Plans`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_pull_form.py` passes

## 3. Give the implement why the whole body limit

Kind: behavior. Reads: `src/devops_cli/roadmap/pull_form.py`, `docs/roadmap/implement.md`, `tests/commands/test_roadmap_step_fix_checks.py`, `tests/core/test_roadmap_implement_planned_run.py`, `tests/roadmap/implement/test_roadmap_implement_body_retry.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`, `tests/roadmap/implement/test_roadmap_implement_job_scoped.py`, `tests/roadmap/implement/test_roadmap_implement_title_sync.py`, `tests/commands/test_roadmap_implement_phases.py`, `tests/commands/test_roadmap_step_fix_conflict.py`, `tests/roadmap/implement/test_roadmap_implement_job_recorded_tests.py`, `tests/roadmap/implement/test_roadmap_implement_phases.py`, `tests/roadmap/implement/test_roadmap_implement_typed_result.py`, `tests/roadmap/implement/test_roadmap_implement_write_stops.py`, `tests/roadmap/test_roadmap_faults.py`. Changes: `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/implement/implement_phases.py`, `src/devops_cli/roadmap/open_row.py`, `tests/core/test_roadmap_implement_planned_run.py`.

- [x] 3.1 Write `test_a_why_of_the_whole_body_limit_is_kept` in `tests/core/test_roadmap_implement_planned_run.py` first: a proposal whose why has 990 characters stays the why of the body, where the base replaces it with the title of the item. It fails on the base, which gives the why a room smaller than the limit by the `Closes` and `Change:` lines
  - Verification: `$ uv run devops ci test tests/core/test_roadmap_implement_planned_run.py` fails on the base
- [x] 3.2 In `_why` of `src/devops_cli/roadmap/implement/implement_run.py`, `_body` of `src/devops_cli/roadmap/implement/implement_phases.py` and `delivery_request` of `src/devops_cli/roadmap/open_row.py` set `room = BODY_MAX_CHARS` instead of the limit less the trailer lines, and state in its docstring that the limit measures the text above `Closes`, so a why of the whole limit fits. Keep the rewrite of the model and the check of `publish` as they are
  - Verification: `$ uv run devops ci test tests/core/test_roadmap_implement_planned_run.py` passes

## 4. Measure the plan check body above Plans

Kind: behavior. Reads: `src/devops_cli/roadmap/pull_form.py`, `docs/roadmap/plan-check.md`, `tests/invariants/test_workflow_contracts.py`, `tests/lang/test_language_catalogs.py`, `tests/roadmap/stage/test_roadmap_stage_plan_check.py`, `tests/roadmap/stage/test_roadmap_stage_drift.py`, `tests/roadmap/test_roadmap_plan_check.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`, `tests/roadmap/refine/test_roadmap_refine_tracker.py`, `tests/roadmap/stage/test_roadmap_stage_held.py`, `tests/roadmap/stage/test_roadmap_stage_module_test_order.py`, `tests/roadmap/stage/test_roadmap_stage_paths.py`, `tests/roadmap/stage/test_roadmap_stage_selection.py`, `tests/roadmap/stage/test_roadmap_stage_trace_subject.py`. Changes: `src/devops_cli/roadmap/plan_check.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_plan_check.py`.

- [x] 4.1 Write `test_a_body_over_the_limit_above_plans_is_reported` in `tests/roadmap/test_roadmap_plan_check.py` first: a text of 1,001 characters above `Plans`, then the `Plans` and `Change:` lines that add 120 characters, gives the `body-length` problem with 1001. Add `test_a_body_at_the_limit_above_plans_has_no_problem` with a text of 1,000 characters, which gets no body-length problem. Both fail on the base, which measures the whole body
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_plan_check.py` fails on the base
- [x] 4.2 In `title_body_problems` of `src/devops_cli/roadmap/plan_check.py` import `measured_body_text` from `pull_form` and measure `len(measured_body_text(body, "Plans"))` in place of `len(body)`. In `src/devops_cli/lang/en/messages.py` change `plan_check_body_long` to "The text above `Plans` has {length} characters, and the limit is {limit}." Update the test that asserts the `body-length` problem of a whole body
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_plan_check.py` passes

## 5. State the measured part in the documents

Kind: other. Reads: `src/devops_cli/roadmap/pull_form.py`, `src/devops_cli/roadmap/plan_check.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`. Changes: `CONTRIBUTING.md`, `docs/roadmap/plan-check.md`.

- [x] 5.1 In `CONTRIBUTING.md` line 181 keep the phrase "in at most 1,000 characters before the trailers" word for word, because `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` reads the number from it, and add after it: ", which is the text above the `Closes` line, and above the `Plans` line in a plan body". In `docs/roadmap/plan-check.md` line 77 say that the limit measures the text above the `Plans` line, and keep the one `Plans #<issue>` line and the rule of the closing keyword
  - Verification: `$ uv run devops ci docs` passes
- [x] 5.2 Edit `CONTRIBUTING.md` and `docs/roadmap/plan-check.md` to name the text that the 1,000-character limit measures
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: Test first: a body whose measured part is just over the limit by the chosen meaning is refused, and the message names the part that it measured. The test fails on the base.
- Group 5: `CONTRIBUTING.md`, the message and the docstring of `body_form_problems` give the same meaning.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

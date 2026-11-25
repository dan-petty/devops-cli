# Tasks

## 1. Behavior

<!-- kind: behavior -->

- [x] 1.1 Add failing tests in `tests/roadmap/test_roadmap_run_job_rows.py` (`test_each_row_runs_in_a_child_span_of_the_round`, `test_the_fix_plan_row_span_carries_its_mode`, `test_a_failed_row_span_has_status_error`, `test_a_row_span_is_the_parent_of_its_model_requests`, `test_the_implement_runner_root_span_carries_the_row`, `test_the_fix_plan_job_root_span_carries_the_row`)
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_run_job_rows.py`
- [x] 1.2 Implement `set_root_span_attribute` (`src/devops_cli/telemetry/tracer.py`, `src/devops_cli/telemetry/__init__.py`), per-row `service.row <name>` child spans in `_execute_due_rows` (`src/devops_cli/roadmap/run.py`), and `service.row` root attributes in runner Job entry points (`src/devops_cli/commands/roadmap.py`, `src/devops_cli/commands/roadmap_step_fix_plan.py`, `src/devops_cli/commands/roadmap_step_fix_checks.py`)
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_run_job_rows.py`

## Workflow follow-up

- Run live Tempo check after release: `{ name = "service.row fix_plan" }` and `{ name = "service.row refine" } >> { span.gen_ai.usage.input_tokens > 0 } | max_over_time(span.gen_ai.usage.input_tokens)`.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

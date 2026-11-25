# Proposal: #5415

## Why

A Service round opens one `service.job <repo>` span (`src/devops_cli/server/service.py:740-748`), so every due roadmap row in `_execute_due_rows` (`src/devops_cli/roadmap/run.py:2166-2185`) shares that round span and Tempo cannot attribute duration or child model requests per row. Separately, runner Jobs (`implement`, `fix_plan`) do not record `service.row` on their root span. Closes #5415.

## What Changes

- Wrap `row.runner` in `_execute_due_rows` (`src/devops_cli/roadmap/run.py`) inside a child span named `service.row <name>` with attributes `service.repo`, `service.row`, `service.result`, and (when `row.name == "fix_plan"`) `service.mode`, setting status `ERROR` on exception while recording no prompt or tool content.
- Track active `SpanHandle` objects in a `ContextVar` in `src/devops_cli/telemetry/tracer.py`, expose `set_root_span_attribute` via `src/devops_cli/telemetry/__init__.py`, and stamp `service.row` onto the root span from the runner Job CLI entry points (`implement`, `fix-plan`, `fix-checks`, and `stage`).
- Add tests covering per-row spans, `fix_plan` `service.mode`, failed row `ERROR` status, child model request parentage, and runner Job root span `service.row` attributes in `tests/roadmap/test_roadmap_run_job_rows.py`.

Because trace span names and attributes are observable Service and runner Job telemetry, this change carries a spec delta for `roadmap-service-spans`. Fits in one pull request; the live Tempo query check runs after merge.

## Capabilities

### New Capabilities

- `roadmap-service-spans`: Per-row child trace spans under `service.job` and root-span `service.row` attributes on runner Jobs.

### Modified Capabilities

None.

## Impact

- Updates `src/devops_cli/telemetry/tracer.py`, `src/devops_cli/telemetry/__init__.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/commands/roadmap_step_fix_plan.py`, and `src/devops_cli/commands/roadmap_step_fix_checks.py`.
- Adds offline telemetry tests in `tests/roadmap/test_roadmap_run_job_rows.py`.

## Feasibility

Confirmed against `origin/main`:

- `src/devops_cli/server/service.py:740-773` opens `service.job <repo>` via `get_tracer().span(...)`.
- `src/devops_cli/roadmap/run.py:2166-2185` executes `row.runner` inside `request_scope(row=row.name)` with no child span; `load_settings` and `_failed_result` already exist in `run.py`.
- `src/devops_cli/telemetry/tracer.py:844-856,1324-1415` activates OpenTelemetry span context on entry so nested `trace_span("ai.llm.chat", ...)` calls (`src/devops_cli/ai/client/unified.py:887`) inherit `parent_span_id` automatically.
- Runner Jobs launch through `main._delegate` (`src/devops_cli/main.py:158`) into `commands/roadmap.py:905-1053` and `commands/roadmap_step_fix_plan.py:74-101`.

## Existing Tool Considered

- `opentelemetry-python` (`open-telemetry/opentelemetry-python`, verdict `in-use`) via `get_tracer()` and `trace_span()`. No external library needed (~150k tokens / 1 hour build; ~50k tokens upkeep). Deletes no code.

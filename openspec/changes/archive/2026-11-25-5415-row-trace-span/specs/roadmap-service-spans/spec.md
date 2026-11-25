## Purpose

Emit per-row child OpenTelemetry spans (`service.row <name>`) under Service rounds and tag runner Job root spans with `service.row` so slow rounds and model requests can be attributed by roadmap row.

## ADDED Requirements

### Requirement: Per-row child span

The Service SHALL run each due roadmap row inside a child span named `service.row <name>` of the round span, setting `service.repo`, `service.row`, and `service.result` without recording prompt or tool content.

#### Scenario: a round with two rows

- **WHEN** `run_due_jobs` executes two due rows inside a round span over `FakeCollector`
- **THEN** two spans named `service.row <name>` are exported with the round span as `parent_span_id` and attributes `service.repo`, `service.row`, and `service.result`

### Requirement: Fix-plan mode attribute

The `service.row fix_plan` span SHALL carry the configured fix-plan mode in attribute `service.mode`.

#### Scenario: a fix_plan row

- **WHEN** `run_due_jobs` executes the `fix_plan` row under a configured `roadmap.fix_plan.mode`
- **THEN** the `service.row fix_plan` span carries `service.mode` equal to that mode

### Requirement: Error status on a failed row

A row whose runner raises an exception SHALL set `STATUS_CODE_ERROR` and `service.result="error"` on its `service.row <name>` span.

#### Scenario: a failed row

- **WHEN** a due row runner raises an exception over `FakeCollector`
- **THEN** the exported `service.row <name>` span has `status_code == "STATUS_CODE_ERROR"` and `service.result == "error"`

### Requirement: Row span parent of model requests

The `service.row <name>` span SHALL remain the active OpenTelemetry span while `row.runner` executes so child model request spans inherit it as their parent.

#### Scenario: a refine row with a model request

- **WHEN** a `refine` row executes an `LLMClient` request over `FakeCollector`
- **THEN** the exported model request span carrying `gen_ai.usage.input_tokens` has the `service.row refine` span as its `parent_span_id`

### Requirement: Runner Job root span attribute

Runner Job CLI entry points for `implement`, `fix_plan`, `fix_checks`, and `stage` SHALL set `service.row` on their root trace span.

#### Scenario: an implement runner Job and a fix-plan Job

- **WHEN** `cli("roadmap", "implement", ...)` and `cli("roadmap", "step", "fix-plan", ...)` execute over `FakeCollector`
- **THEN** each root span (`parent_span_id is None`) has attribute `service.row` set to `"implement"` and `"fix_plan"` respectively

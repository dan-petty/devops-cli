## What happens

`tests/roadmap/test_roadmap_alternatives.py::test_the_decisions_are_cut_by_whole_entries_the_oldest_go_first_and_a_warning_says_so` failed in one full local `devops ci` run on a loaded host. The test passes alone (166 passed in the file) and passes in the four GitHub shards.

## Cause

The test compares the list of ALL warning records with the one expected warning. In the failing run, eight extra records came from the logger `opentelemetry.sdk.trace.export` with the text "Processor is already shutdown, ignoring call". A test that ran before it in the same xdist worker shut a span processor down and left the tracer state behind.

## Expected

The test reads only the records of the logger `devops_cli.roadmap.adr`. The test that leaves the shut processor behind is found and its tracer state is reset.

## Steps

1. Run `uv run devops ci` on a loaded host, or run the telemetry tests and then the file in one worker.
2. Read the assertion at index 4 of the tuple.

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=b9c88de50b05ba257467b9c9e532d380b1d637a8 -->
## Proposed design

### Problem statement
The alternatives ADR cap test failed on a loaded host because it read warnings from other loggers. PR #4077 filters its records by logger name. A telemetry test still shuts down a span processor and leaves tracer state behind, so later tests can emit spurious warnings.

### Acceptance criteria

### Requirement: ADR cap test reads one logger
The alternatives ADR cap test SHALL assert only on log records whose logger name is `devops_cli.roadmap.adr`.

#### Scenario: An unrelated logger warns
- **WHEN** A logger other than `devops_cli.roadmap.adr` emits a warning during the ADR cap test.
- **THEN** The test ignores that warning and asserts only the ADR cap warning.

### Requirement: Telemetry test restores tracer state
The telemetry test that shuts down a span processor SHALL restore the OpenTelemetry tracer state after it runs.

#### Scenario: A later test exports a span
- **WHEN** The telemetry test that shuts down a span processor finishes and a later test exports a span.
- **THEN** No `Processor is already shutdown, ignoring call` warning is logged by `opentelemetry.sdk.trace.export`.

### Requirement: Combined worker run passes
The telemetry tests and the alternatives ADR cap test SHALL pass when they run in one pytest worker.

#### Scenario: Telemetry tests run first
- **WHEN** The telemetry tests and the alternatives ADR cap test run in one pytest worker with the telemetry tests first.
- **THEN** pytest exits with status 0 and the ADR cap test reports no `Processor is already shutdown, ignoring call` warning.

### Existing Tool Considered
No alternatives check has run. pytest's `caplog` fixture covers logger-scoped log capture. The OpenTelemetry `TracerProvider` lifecycle covers tracer-state restore. No new tool or library is necessary.

### Key questions
- **Should the ADR cap test filter captured records by logger name?**: Yes. The test reads only records whose logger name is `devops_cli.roadmap.adr`. Keep that filter and add a regression case for an unrelated warning. (best practice) [sources: tests/roadmap/test_roadmap_alternatives.py]
  - Chosen: Filter by logger name. It isolates the test from warnings of other loggers, including OpenTelemetry.
  - Rejected: Assert every captured warning. It fails when an unrelated logger warns, as the loaded-host run showed.
- **How should the test that shuts down a span processor restore tracer state?**: Use a pytest fixture that saves the global tracer provider before the test and restores it after the test. Do not leave a shut provider in place. (best practice) [sources: tests/support/fakes/otlp.py, tests/roadmap/test_roadmap_alternatives.py]
  - Chosen: Save and restore the provider in a fixture. It restores global state after the test and keeps later tests isolated.
  - Rejected: Reset the provider in each telemetry test. It repeats setup and a new test can miss it.
  - Rejected: Filter later tests only. It hides the leak and keeps cross-test coupling.
- **Should the fix change production code or only tests?**: Change only tests. The failure comes from cross-test state leakage, not from production logging or tracing. (best practice) [sources: tests/roadmap/test_roadmap_alternatives.py]
  - Chosen: Test-only change. It fixes isolation without changing runtime behavior.
  - Rejected: Change production logging or tracing. It adds risk and does not fix the leaked test state.

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->

<!-- devops-roadmap-alternatives:start -->
Alternatives check of 2026-11-10: partly.
Tool: pytest-dev/pytest (https://github.com/pytest-dev/pytest), MIT, last activity 2026-11-09, maintained.
<!-- devops-roadmap-alternatives:end -->

<!-- devops-roadmap-record {"Effort": "Low", "Priority": "P2-Medium", "Status": "Ready", "Value": "Medium", "alternatives.body_hash": "1b666fca678736c8021df877bd45fb8daadee21d1c4d2143bee5d89ff104d126", "alternatives.checked_at": "2026-11-10T01:45:30.870049+00:00", "alternatives.failed_at": null, "alternatives.failed_error": null, "alternatives.tool": "https://github.com/pytest-dev/pytest", "alternatives.verdict": "partly", "refine.alternatives_asked": null, "refine.block_paths": null, "refine.blocked_by": null, "refine.body_hash": "1b666fca678736c8021df877bd45fb8daadee21d1c4d2143bee5d89ff104d126", "refine.failed_body_hash": null, "refine.needs_split": "false", "refine.next_step": "ready", "refine.returned_body_hash": null, "refine.section_hash": "3a4dc1913c9f6a18464aa8e801c33b325c4972957cbe682802b7467b821f5a62"} -->

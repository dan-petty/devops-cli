# Proposal

## Why

Issue #817: devops-cli sends embedding-cache use two times, and both times as single-point gauges. A command is a short-lived process, so a gauge keeps only the value of the last process, and no dashboard can add up the hits and misses.

The gauge pair is one case of a wider fault. `record_metric` sends an OTLP gauge, and 52 call sites in 19 modules under `src/` call it with names that are not in `INSTRUMENTS` (`src/devops_cli/telemetry/instruments.py`). Most of the names are counts or durations, such as `devops_cli_subprocess_seconds` and `devops_cli_vulnerability_lookups_total`. The dashboard tests check what the dashboards read, but nothing checks what the code sends, so an earlier item fixed one or two sites at a time (#816).

## What Changes

- One counter, `devops_cli_embedding_cache_lookups_total`, counts each text that an embedding request looks up, by `result` (`hit` or `miss`). A hit also names its `tier` (`memory` or `valkey`). It replaces the gauges `devops_cli_embedding_cache_hits_total`, `devops_cli_embedding_cache_misses_total` and `devops_cli_embedding_valkey_hits_total`.
- The devops-cli dashboard gets the panel "Embedding Cache Hit Share".
- Each other `record_metric` call site becomes an `emit()` of a declared instrument: a counter for a count, a histogram for a duration, and a gauge for a true snapshot. A name that repeats a declared instrument, or whose value repeats when the same data is read again, is deleted. The design lists each site and its class.
- The gate wait of `devops ci` is the histogram `devops_cli_ci_gate_slot_wait_seconds`, not the gauge `ci.gate_slot_wait_seconds`.
- The module functions `record_metric` and `record_gauge` and the method `OTelTelemetryClient.record_metric` are deleted. `emit()` is the one caller of the client's `increment_counter`, `record_gauge` and `record_histogram`.
- A check in `tests/test_telemetry_instruments.py` fails on any other call that writes a metric by name, and on an `emit()` of an instrument that is not in `INSTRUMENTS`. The Prometheus registry of the Service (`GLOBAL_METRICS`, served on `/metrics`) is a different path and stays out of the check.
- The metric names that devops-cli sends are observable to a dashboard, so the change carries spec deltas: the new capability `metric-instruments`, and a MODIFIED requirement of `ci-gate-admission` for the name of the gate wait.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `metric-instruments`: the metrics that devops-cli sends over OTLP, each declared once in `INSTRUMENTS` and sent through `emit()`.

### Modified Capabilities

- `ci-gate-admission`: the gate wait is the histogram `devops_cli_ci_gate_slot_wait_seconds`.

## Impact

- `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/telemetry/tracer.py`, `src/devops_cli/telemetry/__init__.py`, and the 19 modules that called `record_metric`.
- `src/devops_cli/config/constants.py`: the metric-name constants of the gate wait and of structured output go.
- `k8s/monitoring/dashboards/devops-cli.json`.
- `tests/test_telemetry_instruments.py`, `tests/test_rag_embeddings.py`, and the tests that patched `record_metric` or asserted a deleted name.
- `docs/TELEMETRY.md` (generated), `CONTRIBUTING.md`, and two knowledge-base pages that name the subprocess and subcommand metrics.

## Feasibility

Checked on `origin/main` at bb46660c:

- `rg -n 'record_metric\(|record_gauge\(' src` lists 52 call sites outside `tracer.py`. No file under `k8s/` names any of their metrics (`rg` for each name, with dots read as underscores), so no dashboard or alert rule reads them.
- `emit()` dispatches `InstrumentKind.COUNTER` to `increment_counter`, `GAUGE` to `record_gauge` and `HISTOGRAM` to `record_histogram` on the client. `InstrumentKind.GAUGE` exists since #1253, so the item no longer waits for #974.
- #816 is closed and no `llm_cache` gauge remains, as the 2026-10-08 update of the issue says.
- `_partition_with_valkey_l2` (`src/devops_cli/ai/rag/embeddings.py`) returns the memory hits and the Valkey hits together, and counts the Valkey hits on its own, so each text has one result and, for a hit, one tier.
- `k8s/otel/values.yaml` sends names unchanged (`translation_strategy: UnderscoreEscapingWithoutSuffixes`) and filters no metric, so a new instrument reaches Prometheus under its own name.

## Existing Tool Considered

The OpenTelemetry metrics SDK, which the client already uses, gives the counter, histogram and gauge kinds and their delta export. `INSTRUMENTS` and `emit()` exist already. The change adds no library and builds no new mechanism: it moves the call sites onto the existing declaration and adds one AST check in the test suite, with the `ast` module of the standard library.

The OpenTelemetry GenAI conventions name a duration metric for model calls, `gen_ai.client.operation.duration`. The design records why the chat duration keeps a `devops_cli_` name here.

The change deletes `record_metric` and `record_gauge` from `src/devops_cli/telemetry/tracer.py` and their export from `src/devops_cli/telemetry/__init__.py`, the constants `CONST_CI_GATE_SLOT_WAIT_METRIC` and `CONST_METRIC_AI_STRUCTURED_*`, and 13 call sites whose metrics repeat another metric or count the same data again on a second read.

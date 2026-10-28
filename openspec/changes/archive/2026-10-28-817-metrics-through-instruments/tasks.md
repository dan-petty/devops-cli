# Tasks

## 1. Embedding cache lookups are one counter

- [x] Add failing tests: a request with three memory hits and two misses sends `{result="hit", tier="memory"}` 3 and `{result="miss"}` 2 one time each; a Valkey hit sends `{result="hit", tier="valkey"}` 1
  - Verification: `uv run devops ci test tests/test_rag_embeddings.py`
- [x] Declare `devops_cli_embedding_cache_lookups_total` and the gauge `devops_cli_embedding_cache_size`, emit them from `embed_texts`, and delete the three hit and miss gauges
  - Verification: `uv run devops ci test tests/test_rag_embeddings.py tests/test_telemetry_instruments.py`

## 2. The devops-cli dashboard shows the hit share

- [x] Add a failing test for the query of the panel "Embedding Cache Hit Share"
  - Verification: `uv run devops ci test tests/test_telemetry_instruments.py`
- [x] Add the panel to `k8s/monitoring/dashboards/devops-cli.json`, with the limits of `increase()` in its description
  - Verification: `uv run devops ci test tests/test_telemetry_instruments.py`

## 3. Every metric is a declared instrument sent through emit

- [x] Add the failing instrument check: it fails on a call of a metric method outside `emit()` other than on `GLOBAL_METRICS`, and on an `emit()` of an instrument that `INSTRUMENTS` does not hold; a test shows that it names both kinds of call
  - Verification: `uv run devops ci test tests/test_telemetry_instruments.py`
- [x] Declare the instruments of the design's table, move each call site to `emit()`, and delete the sites that the table deletes, with the constants of their names
  - Verification: `uv run devops ci test tests/test_telemetry_instruments.py tests/test_otel_command_coverage.py tests/test_ci_gate_admission.py tests/test_ci.py tests/test_ai_prewarm.py tests/test_sandbox_metrics.py tests/test_telemetry.py`
- [x] Delete `record_metric` and `record_gauge` from `telemetry/tracer.py`, the method `OTelTelemetryClient.record_metric`, and their export from `telemetry/__init__.py`; the tests that patched `record_metric` read the captured metrics or patch nothing
  - Verification: `uv run devops ci test tests/test_telemetry.py tests/test_ci.py tests/test_ai_prewarm.py tests/test_sandbox_metrics.py`
- [x] Name the new gate wait metric in `CONTRIBUTING.md`, say there that a metric is an `INSTRUMENTS` entry sent with `emit()`, rename the subprocess and subcommand metrics in the knowledge base, and regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme && uv run devops docs check`

## 4. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 817-metrics-through-instruments`
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

## Purpose

The metrics that devops-cli sends over OTLP: each one is declared one time in `INSTRUMENTS` with its kind, and sent through `emit()`, so a dashboard can add up the values that many short-lived processes send.

## ADDED Requirements

### Requirement: Every metric is a declared instrument sent through emit
devops-cli SHALL send each OTLP metric through `emit()` with an instrument that `INSTRUMENTS` holds. No module other than `telemetry/instruments.py` SHALL call a metric method of the telemetry client (`increment_counter`, `record_gauge`, `record_histogram`). The instrument check in `tests/test_telemetry_instruments.py` SHALL name the file and line of each call that breaks the rule.

#### Scenario: The source tree keeps the rule
- **WHEN** the instrument check reads every module under `src/devops_cli/`
- **THEN** it finds no call of a metric method outside `emit()`, and no `emit()` of an instrument that `INSTRUMENTS` does not hold
- **AND** it allows the calls on `GLOBAL_METRICS`, the Prometheus registry that the Service serves on `/metrics`, which sends no OTLP metric

#### Scenario: A module writes a metric by name
- **WHEN** a module calls `get_tracer().record_gauge("devops_cli_example", 1.0)`
- **THEN** the instrument check names that call

#### Scenario: A module emits an undeclared instrument
- **WHEN** a module builds `Instrument("devops_cli_example_total", InstrumentKind.COUNTER, "1", "x")` and passes it to `emit()`
- **THEN** the instrument check names that call

### Requirement: Embedding cache lookups count each text once
`devops_cli_embedding_cache_lookups_total` SHALL count each text that an embedding request looks up, one time, by `result`: `hit` or `miss`. A hit SHALL also carry `tier`: `memory` for the in-process cache, or `valkey` for the Valkey cache. A request SHALL add a value only for a result that has texts. No other metric SHALL count embedding cache hits or misses.

#### Scenario: Three hits and two misses
- **WHEN** an embedding request gets five texts, three of which the in-process cache holds
- **THEN** `devops_cli_embedding_cache_lookups_total` gets the points `{result="hit", tier="memory"}` 3 and `{result="miss"}` 2, one time each

#### Scenario: A hit from Valkey
- **WHEN** an embedding request gets one text that only the Valkey cache holds
- **THEN** `devops_cli_embedding_cache_lookups_total` gets the one point `{result="hit", tier="valkey"}` 1

### Requirement: The devops-cli dashboard shows the embedding cache hit share
The devops-cli dashboard SHALL have the panel "Embedding Cache Hit Share", which divides the embedding cache hits of the last hour by the lookups of the last hour, and shows 0 for an hour with lookups and no hits.

#### Scenario: The panel query
- **WHEN** the panel "Embedding Cache Hit Share" of `k8s/monitoring/dashboards/devops-cli.json` is read
- **THEN** its query is `(sum(increase(devops_cli_embedding_cache_lookups_total{result="hit"}[1h])) or sum(increase(devops_cli_embedding_cache_lookups_total[1h])) * 0) / sum(increase(devops_cli_embedding_cache_lookups_total[1h]))`

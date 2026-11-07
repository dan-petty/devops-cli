# metric-instruments Specification

## Purpose
The metrics that devops-cli sends over OTLP: each one is declared one time in `INSTRUMENTS` with its kind, and sent through `emit()`, so a dashboard can add up the values that many short-lived processes send.

## Requirements

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
- **THEN** its query is `(sum(increase(devops_cli_embedding_cache_lookups_total{job=~"$job",result="hit"}[1h])) or sum(increase(devops_cli_embedding_cache_lookups_total{job=~"$job"}[1h])) * 0) / sum(increase(devops_cli_embedding_cache_lookups_total{job=~"$job"}[1h]))`

### Requirement: The tool-call instruments are declared and documented
`INSTRUMENTS` SHALL hold `devops_cli_roadmap_tool_calls_total` and `devops_cli_roadmap_tool_limit_hits_total` as counters with the unit `1`, `devops_cli_roadmap_tool_answer_chars` as a histogram with the unit `{char}`, and `devops_cli_roadmap_tool_calls_per_run` as a histogram with the unit `{call}`. `docs/TELEMETRY.md` SHALL list each one with its kind and its unit.

#### Scenario: The registry and the document list the four instruments
- **WHEN** a test reads `INSTRUMENTS` and `docs/TELEMETRY.md`
- **THEN** both list the four names with the same kind and the same unit

### Requirement: No instrument attribute is named job or instance
The resource of a process sets the Prometheus labels `job` and `instance`, and a data point attribute with either name is lost. So no `emit()` call SHALL send an attribute named `job` or `instance`. The instrument check SHALL name the file and line of each call that does.

#### Scenario: The source tree keeps the rule
- **WHEN** the instrument check reads every module under `src/devops_cli/`
- **THEN** it finds no `emit()` call with the attribute `job` or `instance`

#### Scenario: A module sends the attribute job
- **WHEN** a module calls `emit(COMMAND_TOTAL, 1.0, {"job": "stage"})`
- **THEN** the instrument check names that call, and it passes `emit(COMMAND_TOTAL, 1.0, {"row": "stage"})`

#### Scenario: A module sends the attribute job in a name or with a double star
- **WHEN** a module sets `labels = {"job": "stage"}` and calls `emit(COMMAND_TOTAL, 1.0, labels)` and `emit(COMMAND_TOTAL, 1.0, {**labels, "x": 1})`
- **THEN** the instrument check names both calls

### Requirement: The devops-cli dashboard shows the tool calls of the planner
`k8s/monitoring/dashboards/devops-cli.json` SHALL have the row "Planner Tools" with the panel "Planner Tool Calls and Answer Size". The panel SHALL chart the calls of each tool by outcome from `devops_cli_roadmap_tool_calls_total`, and the mean answer size of each tool from `devops_cli_roadmap_tool_answer_chars`. Each query SHALL select `job=~"$job"` and `row="stage"`.

#### Scenario: The dashboard JSON holds the tool panel
- **WHEN** a test reads `k8s/monitoring/dashboards/devops-cli.json`
- **THEN** one panel has a query for `devops_cli_roadmap_tool_calls_total` and a query for `devops_cli_roadmap_tool_answer_chars`, each with `job=~"$job"` and `row="stage"`

#### Scenario: The panel reads each series through the function of its kind
- **WHEN** the dashboard checks read the panel
- **THEN** the counter is the first argument of `increase(`, and the histogram is the first argument of `increase(` inside `histogram_avg(`

### Requirement: Alternatives coverage instruments are declared
`INSTRUMENTS` SHALL hold the gauge `devops_cli_roadmap_alternatives_unchecked_items` (unit `1`), the gauge `devops_cli_roadmap_alternatives_oldest_check_age_seconds` (unit `s`) and the histogram `devops_cli_roadmap_alternatives_searches` (unit `1`). The alternatives job SHALL send them through `emit()`, so the instrument check of `tests/telemetry/test_telemetry_instruments.py` covers them.

#### Scenario: The registry holds the three instruments
- **WHEN** a test reads `INSTRUMENTS`
- **THEN** it finds the three names with the kinds gauge, gauge and histogram, and the units `1`, `s` and `1`
- **AND** no name of a gauge ends in `_total`

### Requirement: The devops-cli dashboard shows the alternatives check
The devops-cli dashboard SHALL have the row "Alternatives Check" with the panels "Alternatives Unchecked Items", "Alternatives Oldest Check Age" and "Alternatives Searches per Check". Each query SHALL read its instrument through the function of its kind: a gauge through `last_over_time`, the histogram through `increase`.

#### Scenario: The queries of the three panels
- **WHEN** the panels of the row in `k8s/monitoring/dashboards/devops-cli.json` are read
- **THEN** the queries are `sum by (repo) (last_over_time(devops_cli_roadmap_alternatives_unchecked_items{job=~"$job"}[1d]))`, `max by (repo) (last_over_time(devops_cli_roadmap_alternatives_oldest_check_age_seconds{job=~"$job"}[1d]))`, and `histogram_avg(sum by (verdict) (increase(devops_cli_roadmap_alternatives_searches{job=~"$job"}[1d])))` with `histogram_count` of the same selector

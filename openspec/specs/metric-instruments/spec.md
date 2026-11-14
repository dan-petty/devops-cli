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
`devops_cli_embedding_cache_lookups_total` SHALL count each text that an embedding request looks up, one time, by `result`: `hit` or `miss`. A hit SHALL also carry `tier`: `memory` for the in-process cache, `valkey` for the Valkey cache, or `disk` for the disk cache. A request SHALL add a value only for a result that has texts. No other metric SHALL count embedding cache hits or misses.

#### Scenario: Three hits and two misses
- **WHEN** an embedding request gets five texts, three of which the in-process cache holds
- **THEN** `devops_cli_embedding_cache_lookups_total` gets the points `{result="hit", tier="memory"}` 3 and `{result="miss"}` 2, one time each

#### Scenario: A hit from Valkey
- **WHEN** an embedding request gets one text that only the Valkey cache holds
- **THEN** `devops_cli_embedding_cache_lookups_total` gets the one point `{result="hit", tier="valkey"}` 1

#### Scenario: A hit from the disk cache
- **WHEN** an embedding request gets two texts, one of which only the disk cache holds
- **THEN** `devops_cli_embedding_cache_lookups_total` gets the points `{result="hit", tier="disk"}` 1 and `{result="miss"}` 1, one time each

### Requirement: The devops-cli dashboard shows the embedding cache hit share
The devops-cli dashboard SHALL have the panel "Cache: share of embedding lookups that hit", which divides the embedding cache hits of each window by the lookups of the window, and shows 0 for a window with lookups and no hits. The window SHALL be `$__rate_interval` with a Min step of 15m.

#### Scenario: The panel query
- **WHEN** the panel "Cache: share of embedding lookups that hit" of `k8s/devops/dashboards/devops-cli.json` is read
- **THEN** its query is `(sum(increase(devops_cli_embedding_cache_lookups_total{job=~"$job",result="hit"}[$__rate_interval])) or sum(increase(devops_cli_embedding_cache_lookups_total{job=~"$job"}[$__rate_interval])) * 0) / sum(increase(devops_cli_embedding_cache_lookups_total{job=~"$job"}[$__rate_interval]))`
- **AND** its Min step is 15m

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
`k8s/devops/dashboards/devops-cli.json` SHALL have the row "Planner Tools" with the panel "Planner Tool Calls and Answer Size". The panel SHALL chart the calls of each tool by outcome from `devops_cli_roadmap_tool_calls_total`, and the mean answer size of each tool from `devops_cli_roadmap_tool_answer_chars`. Each query SHALL select `job=~"$job"` and `row="stage"`.

#### Scenario: The dashboard JSON holds the tool panel
- **WHEN** a test reads `k8s/devops/dashboards/devops-cli.json`
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
- **WHEN** the panels of the row in `k8s/devops/dashboards/devops-cli.json` are read
- **THEN** the queries are `sum by (repo) (last_over_time(devops_cli_roadmap_alternatives_unchecked_items{job=~"$job"}[1d]))`, `max by (repo) (last_over_time(devops_cli_roadmap_alternatives_oldest_check_age_seconds{job=~"$job"}[1d]))`, and `histogram_avg(sum by (verdict) (increase(devops_cli_roadmap_alternatives_searches{job=~"$job"}[1d])))` with `histogram_count` of the same selector

### Requirement: The row seconds histogram is declared and documented
`INSTRUMENTS` SHALL hold `devops_cli_roadmap_row_seconds` as a histogram with the unit `s` and the attributes `repo`, `row` and `result`, and `lane` in a round of the Service. `docs/TELEMETRY.md` SHALL list it. One repository SHALL add at most 39 series: 13 rows x 3 results, because each row is in one lane only, and the buckets add no series.

#### Scenario: The registry and the document list the histogram
- **WHEN** a test reads `INSTRUMENTS` and `docs/TELEMETRY.md`
- **THEN** both list `devops_cli_roadmap_row_seconds`, and the registry gives the kind histogram and the unit `s`

#### Scenario: The series of one repository are bounded
- **WHEN** a test counts the rows of the due table and the results of a job
- **THEN** it finds 13 rows and 3 results

### Requirement: Each row that ran adds its seconds
A round of the roadmap SHALL send one sample of `devops_cli_roadmap_row_seconds` for each row that ran, with the seconds of its runner and the attributes `repo`, `row` and `result`, and `lane` when the round has a lane. The `result` SHALL be `success`, `error` or `stopped`, with the same meaning as in `devops_cli_service_jobs_total`. A row that is not due, a row that the failure ledger suspends and a row that a clone failure keeps from running SHALL add no sample.

#### Scenario: Two rows run
- **WHEN** a round of the lane `status` runs the rows `metrics` and `implement`, and the first takes 2.5 seconds and the second 7 seconds
- **THEN** the collector receives one sample of 2.5 seconds with `row` `metrics` and `result` `success`, and one of 7 seconds with `row` `implement` and `result` `success`, each with the attribute `repo` and the attribute `lane` `status`

#### Scenario: A row is not due or is suspended
- **WHEN** a round has a row that no trigger makes due, and a row that failed its limit of rounds on the same input
- **THEN** neither row adds a sample in that round

#### Scenario: A clone failure keeps a row from running
- **WHEN** the clone of the repository fails and the rows of the round need it
- **THEN** no runner is called and the histogram receives no sample

#### Scenario: A row raises
- **WHEN** a row takes 4 seconds and then raises an error
- **THEN** the collector receives a sample of 4 seconds with `result` `error`, and with `result` `stopped` when the error is the stop of the Service

#### Scenario: A run with no lane
- **WHEN** a run with no lane, such as one of the command line, runs a row
- **THEN** the collector receives the sample of that row with no attribute `lane`

### Requirement: The step seconds histogram and the gate refusal counter are declared and documented
`INSTRUMENTS` SHALL hold the histogram `devops_cli_roadmap_step_seconds` (unit `s`, attributes `repo`, `row`, `step`, `result`) and the counter `devops_cli_roadmap_stage_gate_refusals_total` (unit `1`, attributes `repo`, `gate`). `docs/TELEMETRY.md` SHALL list both. One repository SHALL add at most 10 series to the histogram for the stage row (5 steps, 2 results) and 16 to the counter (one for each `ProposalGate`). The buckets SHALL add none.

#### Scenario: The registry and the document list both instruments
- **WHEN** a test reads `INSTRUMENTS` and `docs/TELEMETRY.md`
- **THEN** both list `devops_cli_roadmap_step_seconds` and `devops_cli_roadmap_stage_gate_refusals_total`, and the registry gives the kind histogram with the unit `s` and the kind counter with the unit `1`

#### Scenario: The instrument texts state the series counts
- **WHEN** a test reads the description of each instrument
- **THEN** the histogram text holds "10 series" and the counter text holds the number of members of `ProposalGate` and the word "series"

### Requirement: Each step of a stage round adds its seconds
A stage round SHALL send one sample of `devops_cli_roadmap_step_seconds` for each call of a step, with the attributes `repo`, `row` `stage`, `step` and `result`. The `step` SHALL be `select`, `plan`, `gate`, `review` or `apply`. The `result` SHALL be `error` when the step raised an error, else `ok`: a plan that a gate refuses is `ok`. A job with no review call sends no `review` sample, and a replay of the golden set, which has no repository, sends none.

#### Scenario: A round plans, reviews and writes one item
- **WHEN** a round plans one item whose planner call takes 3 seconds and whose review takes 2 seconds, and the writer writes the item
- **THEN** the collector receives one sample for each of `select`, `plan`, `gate`, `review` and `apply` with `row` `stage` and `result` `ok`, the `plan` sample holds 3 seconds, and the `review` sample holds 2 seconds

#### Scenario: A refused reply
- **WHEN** a gate refuses the first reply and the second reply passes
- **THEN** the item adds two `plan` samples and two `gate` samples, and every `gate` sample has the result `ok`

#### Scenario: A step raises
- **WHEN** the planner call takes 3 seconds and then raises an error
- **THEN** the collector receives a `plan` sample of 3 seconds with `result` `error`, and no sample for a later step

#### Scenario: A write fails
- **WHEN** the writer fails to open the pull request of an item
- **THEN** the collector receives an `apply` sample with `result` `error`

#### Scenario: A replay of the golden set
- **WHEN** `plan_item` plans one item with no repository
- **THEN** the collector receives no step sample and no refusal

### Requirement: Each gate that refuses a reply adds one to the gate refusal counter
The stage planner SHALL add 1 to `devops_cli_roadmap_stage_gate_refusals_total` for each gate of `check_gates` that finds a problem in a reply, with the attributes `repo` and `gate`. The `gate` SHALL be the value of a `ProposalGate` member. A gate that finds several problems in one reply SHALL add 1. A gate that finds none SHALL add nothing.

#### Scenario: One gate refuses
- **WHEN** a reply changes two files that do not exist and the next reply passes every gate
- **THEN** the counter holds 1 for the gate `paths` and no point for any other gate

#### Scenario: A plan passes every gate
- **WHEN** the first reply passes every gate
- **THEN** the counter has no point

#### Scenario: A gate refuses two replies
- **WHEN** the same gate refuses the first reply and the reply that answers it
- **THEN** the counter holds 2 for that gate

### Requirement: The intake outcome counter is declared and documented
`INSTRUMENTS` SHALL hold the counter `devops_cli_roadmap_intake_candidates_total` (unit `1`, attributes `repo` and `result`). The `result` SHALL be `placed`, `duplicate`, `skipped` or `failed`. `docs/TELEMETRY.md` SHALL list the counter. One repository SHALL add 4 series, and the text of the instrument SHALL say "4 series".

#### Scenario: The registry and the document list the counter
- **WHEN** a test reads `INSTRUMENTS` and `docs/TELEMETRY.md`
- **THEN** both list `devops_cli_roadmap_intake_candidates_total`, the registry gives the kind counter with the unit `1`, and the text holds "4 series"

### Requirement: Each intake candidate counts once under its result
`apply_intake` SHALL take the keyword `repo` and SHALL add 1 to `devops_cli_roadmap_intake_candidates_total` for each candidate of the plan, with the attributes `repo` and `result`. A candidate that intake wrote with no possible duplicate SHALL count as `placed`, and one that it wrote with a possible duplicate SHALL count as `duplicate` and not as `placed`.

#### Scenario: Each outcome counts once
- **WHEN** a test runs `apply_intake` over four candidates that give the results `placed`, `duplicate`, `skipped` and `failed`
- **THEN** the counter holds 1 for each result, under the repository of the round

#### Scenario: A possible duplicate is placed
- **WHEN** the model names an Item as the possible original of a candidate
- **THEN** intake places the candidate, and the counter holds 1 for `duplicate` and 0 for `placed`

### Requirement: A candidate that is not written counts as skipped or failed
A candidate with the outcome skip, or whose Item a person changed since the plan, SHALL count as `skipped`. A candidate whose write raised `GitHubOperationError` SHALL count as `failed`. An error for a rate limit or a refused token SHALL go on, and the candidates that it keeps from running SHALL count nothing.

#### Scenario: An Item that a person changed
- **WHEN** a person changes the Item of a candidate between the plan and the write
- **THEN** the counter holds 1 for `skipped` and 0 for `failed`

#### Scenario: A rate limit
- **WHEN** the write of the second of three candidates raises a rate limit error
- **THEN** the error goes on, the counter holds 1 for `placed`, and the third candidate counts nothing

### Requirement: The intake round starts its four series at zero
The intake round SHALL add 0 to `devops_cli_roadmap_intake_candidates_total` for each of the four results of its repository before the first candidate, also when the round writes nothing.

#### Scenario: A round with no candidate
- **WHEN** the intake round runs over a repository with no candidate
- **THEN** the counter holds 0 for each of the four results

#### Scenario: A round with one candidate
- **WHEN** the intake round places one candidate
- **THEN** the counter holds 1 for `placed` and 0 for the other three results

### Requirement: The implement job sends the seconds of its checks, its publish and its watch
The implement job SHALL send one sample of `devops_cli_roadmap_step_seconds` with the attributes `repo`, `row` `implement`, `step` and `result` for each call of the scoped checks (`checks`), for each publish of a branch (`publish`) and for each watch of the checks of the pull request (`watch`). The `result` SHALL be `error` when the step raised an error, and for a watch also when it returns a check that failed; else `ok`.

#### Scenario: A run sends one sample for each step
- **WHEN** a test runs the implement job over a Staged item and over a Planned item with passing checks
- **THEN** the histogram holds one sample for each of `checks`, `publish` and `watch` with `row` `implement` and `result` `ok`

#### Scenario: Scoped checks that no fix repairs
- **WHEN** a scoped check fails after the last fix round
- **THEN** the histogram holds one `checks` sample with `result` `error`, and no `publish` and no `watch` sample

#### Scenario: A failed check of the pull request
- **WHEN** the first watch returns a failed check and the watch after the repair passes
- **THEN** the histogram holds one `watch` sample with `result` `error` and one with `result` `ok`, and two `checks` and two `publish` samples with `result` `ok`

### Requirement: The publish sample excludes the checks and the push of a stop
The `publish` sample SHALL cover only the push and the draft pull request, and SHALL NOT cover the scoped checks. The push of a stop of the job SHALL send no sample.

#### Scenario: Publish excludes the checks
- **WHEN** the scoped checks take 10 seconds and the push takes 2 seconds
- **THEN** the `checks` sample holds at least 10 seconds and the `publish` sample holds less than 10 seconds

### Requirement: The implement series are counted in the text of the instrument
One repository SHALL add 6 series for the implement row (3 steps, 2 results), and the buckets SHALL add none. The text of the instrument SHALL say "6 series", and `docs/TELEMETRY.md` SHALL hold it.

#### Scenario: The text states the series counts
- **WHEN** a test reads the text of the histogram and `docs/TELEMETRY.md`
- **THEN** both hold "6 series" for the implement row and "10 series" for the stage row

### Requirement: An upstream status gauge holds one series for each service and component
`emit_service_status_telemetry` SHALL send `devops_cli_upstream_service_status` with the label `service` only, and `devops_cli_upstream_component_status` with the labels `service` and `component` only. The value holds the indicator or the component status, so a new status replaces the value of the one series.

#### Scenario: The indicator of a service changes
- **WHEN** GitHub reports the indicator `major` and then `none`
- **THEN** the export holds one series of `devops_cli_upstream_service_status` with `service=github`, and its last value is 0

#### Scenario: The status of a component changes
- **WHEN** the GitHub component `Actions` goes from `major_outage` to `operational`
- **THEN** the export holds one series of `devops_cli_upstream_component_status` for `Actions`, and its last value is 0

### Requirement: The decision point duration and failed instruments are declared and documented
`INSTRUMENTS` SHALL hold the histogram `devops_cli_decision_point_duration_seconds`, with the unit `s` and the attributes `point` and `resolver`, and the counter `devops_cli_decision_point_failed_total`, with the unit `1` and the attributes `point` and `error`. `docs/TELEMETRY.md` SHALL list both. The description of each instrument SHALL state its per-point bound: 3 series for the histogram and 7 for the counter.

#### Scenario: The registry and the document list both instruments
- **WHEN** A test reads `INSTRUMENTS` and the telemetry document
- **THEN** Both list `devops_cli_decision_point_duration_seconds` as a histogram with the unit `s` and `devops_cli_decision_point_failed_total` as a counter with the unit `1`

#### Scenario: The instrument texts state the series counts
- **WHEN** A test reads the description of each of the two instruments
- **THEN** The histogram text holds `3 series` and the counter text holds `7 series`

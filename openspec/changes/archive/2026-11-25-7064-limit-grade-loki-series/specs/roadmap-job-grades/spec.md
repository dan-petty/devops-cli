## MODIFIED Requirements

### Requirement: eval grades reads the result lines with metric instant queries
`devops roadmap eval grades` SHALL read the result lines with LogQL metric instant queries on `/loki/api/v1/query` of the Loki that `--loki-url` or `loki.url` names. `--repo` SHALL put a match of the repository in each query. `--dry-run` SHALL send no request and print each query.

#### Scenario: The dry run sends no request
- **WHEN** a person runs `devops roadmap eval grades --dry-run`
- **THEN** the command sends 0 requests and prints each LogQL query with the Loki address of `loki.url`

#### Scenario: Loki refuses a query
- **WHEN** Loki answers a query with HTTP 400 and no series-limit message
- **THEN** the report stops with `ServiceRequestError` and the status 400

## ADDED Requirements

### Requirement: Counts query label set
The `COUNTS` grade query SHALL include a `keep` stage before its window range whose labels equal its `sum by` labels (`roadmap_job, repo, version, success, infra`).

#### Scenario: Seven-day counts query
- **WHEN** `plan_grade_queries(GradeWindow.D7)` builds the `COUNTS` query
- **THEN** the expression includes `| keep roadmap_job, repo, version, success, infra [7d]` before the range closing brace

### Requirement: Classes query label set
The `CLASSES` grade query SHALL include `success="false"` and `infra="false"` filters and a `keep` stage retaining its `sum by` labels plus `success` and `infra`.

#### Scenario: Seven-day classes query
- **WHEN** `plan_grade_queries(GradeWindow.D7)` builds the `CLASSES` query
- **THEN** the expression keeps `success="false"` and `infra="false"` filters and ends the log pipeline with `| keep roadmap_job, repo, failure_class, success, infra`

### Requirement: Drafted query label set
The `DRAFTED` grade query SHALL keep `roadmap_job`, `result`, and `infra` filters and include a `keep` stage whose labels equal `repo, item, pull, repair_rounds`.

#### Scenario: Seven-day drafted query
- **WHEN** `plan_grade_queries(GradeWindow.D7)` builds the `DRAFTED` query
- **THEN** the expression keeps the implement drafted and infra filters and includes `| keep repo, item, pull, repair_rounds [7d]`

### Requirement: First-passes query label set
The `FIRST_PASSES` grade query SHALL keep `success="true"` and `infra="false"` filters and include a `keep` stage whose labels equal its `sum by` labels.

#### Scenario: Seven-day first-passes query
- **WHEN** `plan_grade_queries(GradeWindow.D7)` builds the `FIRST_PASSES` query
- **THEN** the expression keeps `success="true"` and `infra="false"` filters and includes `| keep roadmap_job, repo, ...` with `_FIRST_PASS_COUNTS`

### Requirement: Efficiency query label set
Each efficiency grade query SHALL include a `keep` stage retaining `roadmap_job, repo` and its unwrapped count label before `| unwrap`.

#### Scenario: Seven-day efficiency query
- **WHEN** `plan_grade_queries(GradeWindow.D7)` builds each efficiency query
- **THEN** the pipeline includes `| keep roadmap_job, repo, <count> | unwrap <count>` before `[7d]`

### Requirement: Split on the series limit
A count grade query SHALL split its window in half down to a `1h` floor and sum the partial vectors when Loki returns HTTP 400 with `maximum number of series`.

#### Scenario: Counts query on a store over the series limit
- **WHEN** Loki answers the `[7d]` `COUNTS` query with HTTP 400 naming `maximum number of series` and answers both `[84h]` half-window queries
- **THEN** `grade_report` queries both `[84h]` halves at `end - 84h` and `end` and returns their summed counts

### Requirement: No split on another 400
The report SHALL NOT split a query when Loki returns HTTP 400 without `maximum number of series`.

#### Scenario: A query with a syntax error
- **WHEN** Loki answers HTTP 400 with `parse error`
- **THEN** `grade_report` sends one query and raises `ServiceRequestError` with status 400

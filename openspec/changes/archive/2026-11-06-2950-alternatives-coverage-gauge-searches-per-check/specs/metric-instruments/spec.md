## ADDED Requirements

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

## ADDED Requirements

### Requirement: The decision point duration and failed instruments are declared and documented
`INSTRUMENTS` SHALL hold the histogram `devops_cli_decision_point_duration_seconds`, with the unit `s` and the attributes `point` and `resolver`, and the counter `devops_cli_decision_point_failed_total`, with the unit `1` and the attributes `point` and `error`. `docs/TELEMETRY.md` SHALL list both. The description of each instrument SHALL state its per-point bound: 3 series for the histogram and 6 for the counter.

#### Scenario: The registry and the document list both instruments
- **WHEN** A test reads `INSTRUMENTS` and the telemetry document
- **THEN** Both list `devops_cli_decision_point_duration_seconds` as a histogram with the unit `s` and `devops_cli_decision_point_failed_total` as a counter with the unit `1`

#### Scenario: The instrument texts state the series counts
- **WHEN** A test reads the description of each of the two instruments
- **THEN** The histogram text holds `3 series` and the counter text holds `6 series`

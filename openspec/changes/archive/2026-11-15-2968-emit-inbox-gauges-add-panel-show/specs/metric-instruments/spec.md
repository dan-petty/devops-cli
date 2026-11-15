## ADDED Requirements

### Requirement: The inbox gauge is declared and documented
The instruments module SHALL declare `devops_cli_roadmap_inbox_items` as a gauge with unit `1` and list it in `INSTRUMENTS`. The description SHALL name the labels `repo` and `kind`. The telemetry document SHALL list the gauge with its kind and unit.

#### Scenario: The instrument list holds the inbox gauge
- **WHEN** The telemetry instruments are listed
- **THEN** The list holds `devops_cli_roadmap_inbox_items` with kind Gauge, unit `1` and a description naming `repo` and `kind`, and `uv run devops ci docs` reports no error

### Requirement: The metrics row and inbox command send the count of each counted kind
`emit_inbox_counts` SHALL send one value of `devops_cli_roadmap_inbox_items` for each kind of `COUNTED_KINDS`, with the repository as the label `repo` and the kind as `kind`. The metrics row and `inbox_cmd` SHALL call it.

#### Scenario: Fake repository with known counts
- **WHEN** A fake repository returns two `blocked` lines and one `refine` line, and no line of the other counted kinds
- **THEN** The emitted points show 2 for `blocked`, 1 for `refine` and 0 for each other counted kind, with the repository name in `repo`

### Requirement: The inbox gauge holds one series for each counted kind of each repository
`devops_cli_roadmap_inbox_items` MUST hold one series for each counted kind of each repository. The counted kinds SHALL be `blocked`, `refine`, `split`, `alternatives`, `failed`, `stage_retry`, `claim`, and `labels`. Seven repositories SHALL give at most 56 series.

#### Scenario: One repository
- **WHEN** The inbox of one repository is sent
- **THEN** The gauge holds eight series, one for each counted kind

#### Scenario: Seven repositories
- **WHEN** The inbox of seven repositories holding a line of each counted kind is sent
- **THEN** The gauge holds at most 56 series, and each series has a `repo` label and a `kind` label

### Requirement: Person cause telemetry and alerts
The instruments module SHALL declare instruments for inflow, outflow, and age of typed person causes. An alert rule SHALL trigger when person cause daily inflow exceeds the daily cap.

#### Scenario: Person cause instruments declared
- **WHEN** Telemetry instruments are listed
- **THEN** The list holds counters for inflow and outflow and a gauge for age of typed person causes

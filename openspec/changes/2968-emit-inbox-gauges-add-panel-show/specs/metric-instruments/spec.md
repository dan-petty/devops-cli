## ADDED Requirements

### Requirement: The inbox gauge is declared and documented
The instruments module SHALL declare `devops_cli_roadmap_inbox_items` as a gauge with the unit `1` and SHALL list it in `INSTRUMENTS`. The description of the gauge SHALL name the labels `repo` and `kind`. The telemetry document SHALL list the gauge with its kind and its unit.

#### Scenario: The instrument list holds the inbox gauge
- **WHEN** The telemetry instruments are listed
- **THEN** The list holds `devops_cli_roadmap_inbox_items` with kind Gauge, unit `1` and a description that names `repo` and `kind`, and `uv run devops ci docs` reports no error

### Requirement: The inbox command sends the count of each counted kind
`emit_inbox_counts` SHALL send one value of `devops_cli_roadmap_inbox_items` for each kind of `COUNTED_KINDS`, with the repository as the label `repo` and the kind as the label `kind`, and SHALL send 0 for a kind that has no line. `inbox_cmd` SHALL call it after `read_inbox` returns and before it renders the report.

#### Scenario: Fake repository with known counts
- **WHEN** A fake repository returns two `blocked` lines and one `refine` line, and no line of the other counted kinds
- **THEN** The emitted points show 2 for `blocked`, 1 for `refine` and 0 for each other counted kind, and each point carries the repository name in `repo`

### Requirement: The inbox gauge holds one series for each counted kind of each repository
`devops_cli_roadmap_inbox_items` MUST hold one series for each counted kind of each repository that the inbox command reads, and no other series. The counted kinds SHALL be `blocked`, `refine`, `split`, `alternatives`, `failed`, `stage_retry`, `claim`, `labels` and `queue`. Seven repositories SHALL give at most 63 series.

#### Scenario: One repository
- **WHEN** The inbox of one repository is sent
- **THEN** The gauge holds nine series, one for each counted kind

#### Scenario: Seven repositories
- **WHEN** The inbox of seven repositories that hold a line of each counted kind is sent
- **THEN** The gauge holds at most 63 series, and each series has a `repo` label of one of the seven repositories and a `kind` label of a counted kind

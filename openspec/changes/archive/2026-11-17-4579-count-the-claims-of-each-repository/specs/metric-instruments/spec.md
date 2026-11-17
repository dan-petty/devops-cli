## ADDED Requirements

### Requirement: The claims gauge is declared and documented
The telemetry module SHALL define `devops_cli_roadmap_claims` as a gauge with unit `1`.

#### Scenario: The gauge is registered
- **WHEN** a test imports `INSTRUMENTS` from `devops_cli.telemetry.instruments`
- **THEN** the tuple holds `devops_cli_roadmap_claims` with kind `GAUGE` and unit `1`, and the generated metric table of `docs/TELEMETRY.md` lists it

### Requirement: Each claimant kind gets a sample
A snapshot SHALL send one `devops_cli_roadmap_claims` sample for each claimant kind, with 0 for a kind that holds no open item.

#### Scenario: Each kind gets a sample
- **WHEN** one open item holds `owner/Service` and no item holds `owner/Agent` or `owner/Human`
- **THEN** the snapshot sends `claimant="service"` with 1, and `claimant="agent"` and `claimant="human"` with 0

### Requirement: One read of the store
The snapshot MUST read the items of the store once and send no extra GitHub request for the gauge.

#### Scenario: The request count is unchanged
- **WHEN** the metrics row collects a report that holds the gauge
- **THEN** the GitHub requests that the fake client recorded equal those of a report without the gauge

### Requirement: Label values
A series of the gauge MUST hold no issue number and no label named `owner`.

#### Scenario: The label sets are checked
- **WHEN** the snapshot sends the series of the gauge
- **THEN** each label name is `repo` or `claimant`, and no value is an issue number

### Requirement: A failed read sends nothing
A snapshot whose read of the items fails MUST send no sample of the gauge.

#### Scenario: The store raises
- **WHEN** the read of the label events raises `GitHubOperationError`
- **THEN** the snapshot sends no sample of the gauge, and the report holds an empty claim map

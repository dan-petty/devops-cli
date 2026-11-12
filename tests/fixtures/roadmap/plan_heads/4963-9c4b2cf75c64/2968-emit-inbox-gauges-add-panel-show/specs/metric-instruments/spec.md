## ADDED Requirements

### Requirement: The inbox gauge is declared with the repo and kind labels
devops-cli SHALL declare `devops_cli_roadmap_inbox_items` as a gauge of unit `1` in `src/devops_cli/telemetry/instruments.py`, add it to `INSTRUMENTS`, and name the labels `repo` and `kind` in its description.

#### Scenario: The instrument list holds the inbox gauge
- **WHEN** The telemetry instruments are listed
- **THEN** The list holds `devops_cli_roadmap_inbox_items` as a gauge of unit `1`, and its description names `repo` and `kind`

### Requirement: Each repository sends one inbox value for each kind
`devops roadmap inbox` SHALL send one value of `devops_cli_roadmap_inbox_items` for each kind of `InboxKind` of each repository that it reads, with the repository name and the kind as labels, and SHALL send 0 for a kind that has no line.

#### Scenario: A fake repository with two blocked lines and one refine line
- **WHEN** A fake repository returns two `blocked` lines, one `refine` line and no line of any other kind
- **THEN** The gauge holds 2 for `blocked`, 1 for `refine` and 0 for each other kind, and each series carries the repository name

## ADDED Requirements

### Requirement: Alternatives coverage instruments
The metrics module SHALL declare the gauge `devops_cli_roadmap_alternatives_unchecked_items`, the gauge `devops_cli_roadmap_alternatives_oldest_check_age_seconds` and the histogram `devops_cli_roadmap_alternatives_searches` in `INSTRUMENTS`, so the invariant that every metric is a declared instrument covers them.

#### Scenario: The invariant covers the new instruments
- **WHEN** The three instruments are added to `INSTRUMENTS`
- **THEN** `tests/telemetry/test_telemetry_instruments.py` passes with no change to its list of instruments

#### Scenario: An undeclared metric fails the invariant
- **WHEN** A module writes `devops_cli_roadmap_alternatives_searches` by name without an entry in `INSTRUMENTS`
- **THEN** `tests/telemetry/test_telemetry_instruments.py` fails

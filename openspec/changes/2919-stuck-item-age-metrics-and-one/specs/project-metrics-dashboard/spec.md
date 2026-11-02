## ADDED Requirements

### Requirement: The dashboard shows the roadmap item age
The project-metrics dashboard SHALL hold a panel that reads the roadmap age gauges by state and repository.

#### Scenario: The panel query names a declared instrument
- **WHEN** The dashboard queries are checked against INSTRUMENTS
- **THEN** The age panel query names a declared age gauge

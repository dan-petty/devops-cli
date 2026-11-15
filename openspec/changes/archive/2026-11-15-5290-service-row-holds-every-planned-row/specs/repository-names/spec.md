## ADDED Requirements

### Requirement: The rows of the roadmap Service are name segments
`ServiceRow` SHALL hold `implement`, `stage`, `refine`, `alternatives`, `intake`, `sweep`, `metrics`, `brain`, `resolve`, `group`, `split`, `watch`, `fix-checks`, `fix-conflict` and `fix-plan`. Each value SHALL be a name segment of at most 12 characters, and no value SHALL be `repair`.

#### Scenario: Each row fits a name
- **WHEN** a test reads each value of `ServiceRow`
- **THEN** each value has at most 12 characters and `is_name_segment` accepts it

#### Scenario: The planned rows are present
- **WHEN** a test reads the values of `ServiceRow`
- **THEN** they hold `brain`, `resolve`, `group`, `split`, `watch`, `fix-checks`, `fix-conflict` and `fix-plan`, and not `repair`

## ADDED Requirements

### Requirement: Model request duration
The spend hook of `build_agent` SHALL record the seconds of each model request in `duration_seconds`, measured with a monotonic clock. It SHALL record one duration for each request, and SHALL write no spend record for a request that raises an error.

#### Scenario: One request
- **WHEN** a run on a fake model has a monotonic clock of 10.0 before the request and 10.25 after it
- **THEN** the newest record has `duration_seconds` 0.25

#### Scenario: Two requests in one run
- **WHEN** a run has monotonic readings 1.0, 1.2, 2.0 and 2.5
- **THEN** the two records have `duration_seconds` 0.2 and 0.5

#### Scenario: A failed request
- **WHEN** the model raises an error
- **THEN** the ledger holds no new record, and the start time does not carry to the next request

### Requirement: Mean duration report
The backend breakdown of the lifetime spend report SHALL give `mean_duration_seconds` as the mean of the recorded durations of the records of a backend.

#### Scenario: Two recorded durations
- **WHEN** two records of one backend have durations 0.1 and 0.3
- **THEN** the backend summary has `mean_duration_seconds` 0.2

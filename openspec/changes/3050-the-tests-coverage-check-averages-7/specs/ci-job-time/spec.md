## ADDED Requirements

### Requirement: duration-window-size
The `Test Job Duration` job SHALL read the last 20 completed pushes to `main` and SHALL fail when the mean duration of the `Tests & Coverage` job exceeds 300 seconds.

#### Scenario: window reads 20 runs
- **WHEN** The job is invoked with a mocked Actions API returning 25 completed pushes
- **THEN** It selects the last 20 pushes and computes the mean from those 20.

#### Scenario: job fails above bound
- **WHEN** The mocked API returns 20 pushes with a mean duration of 350 seconds
- **THEN** The job exits with a non-zero status and reports the mean of 350 seconds.

#### Scenario: job passes below bound
- **WHEN** The mocked API returns 20 pushes with a mean duration of 280 seconds
- **THEN** The job exits with zero status and reports the mean of 280 seconds.

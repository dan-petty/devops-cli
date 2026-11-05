## ADDED Requirements

### Requirement: Each paced GitHub request names the HTTP status of its answer

The request counter SHALL name the HTTP status of the answer to each paced GitHub request in its `status` label. A request that gets no answer, and a gh command, SHALL name the status `none`.

#### Scenario: A 304 answer counts with its status
- **WHEN** the GitHub session sends a conditional GET and GitHub answers 304.
- **THEN** the counter has one sample for that attempt with `status` `304`.

#### Scenario: A gh command counts with status none
- **WHEN** the rate limiter paces a gh command.
- **THEN** the counter has one sample for that attempt with `status` `none`.

### Requirement: The rate limiter logs its pace lines at DEBUG

The rate limiter SHALL log each mandatory pause and each quota window reset at DEBUG level.

#### Scenario: A mandatory pause is logged at DEBUG
- **WHEN** the rate limiter delays a request for its quota.
- **THEN** the pause record has level DEBUG, and no record of that pause has level INFO.

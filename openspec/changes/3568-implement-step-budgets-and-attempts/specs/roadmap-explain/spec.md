## ADDED Requirements

### Requirement: The trace option prints an attempt
`explain <issue> --trace` SHALL print an `attempt` event as one line with its step, its number, its outcome, its failure class, its evidence and what follows.

#### Scenario: An attempt
- **WHEN** the trace holds the attempt 1 of `group 1` that failed with class `lint` and is followed by `repair`
- **THEN** the output line names `group 1`, attempt 1, the outcome `failed`, the class `lint` and `repair`

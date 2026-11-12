## RENAMED Requirements

- FROM: `### Requirement: A stop that no rule clears costs one request in each round`
- TO: `### Requirement: A stop that no rule clears lists its comments only after a change`

## MODIFIED Requirements

### Requirement: A stop that no rule clears lists its comments only after a change
The round SHALL list the comments of a Blocked stop only when the `updated_at` of the issue is not the one of the last listing that the process holds for it, and SHALL read the issue again only when a rule holds. It SHALL read the template at most one time, also when the read fails.

#### Scenario: Three stops that nothing clears
- **WHEN** three items are Blocked and no rule clears them, in the first round of a process
- **THEN** the round sends three listings of comments and reads no issue

#### Scenario: A later round with no change
- **WHEN** a later round finds the same three stops with the same `updated_at`
- **THEN** the round sends no listing of comments

#### Scenario: A retry after the first round
- **WHEN** the owner comments `implement: retry` on one of the stops
- **THEN** the next round lists the comments of that issue only, and clears its stop

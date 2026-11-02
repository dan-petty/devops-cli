## ADDED Requirements

### Requirement: First-pass limit applies while items lack a check
While at least one open item has no check, the alternatives row SHALL check at most `roadmap.alternatives.first_pass_limit` items in a round.

#### Scenario: 25 open items have no check
- **WHEN** The alternatives row runs and 25 open items have no check
- **THEN** The row checks at most 20 items in that round

### Requirement: Recheck limit applies when all items have a check
When every open item has a check, the alternatives row SHALL check at most `roadmap.alternatives.limit` items in a round.

#### Scenario: All open items have a check
- **WHEN** The alternatives row runs and every open item already has a check
- **THEN** The row checks at most 5 items in that round

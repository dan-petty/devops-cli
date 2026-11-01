## ADDED Requirements

### Requirement: service-pause-gauge
The roadmap Service SHALL send devops_cli_service_paused_until_seconds as a gauge with the Unix time the round pause ends, or 0 when no pause holds.

#### Scenario: paused round
- **WHEN** a round pauses and the Service logs the pause end time
- **THEN** the captured gauge devops_cli_service_paused_until_seconds equals the Unix time the pause ends

#### Scenario: unpaused round
- **WHEN** a round completes with no pause
- **THEN** the captured gauge devops_cli_service_paused_until_seconds equals 0

### Requirement: graphql-remaining-gauge
The roadmap Service SHALL send devops_cli_github_graphql_remaining as a gauge with the GraphQL points left from each round's closing budget read.

#### Scenario: budget read
- **WHEN** a round's closing budget read completes
- **THEN** the captured gauge devops_cli_github_graphql_remaining equals the remaining GraphQL points

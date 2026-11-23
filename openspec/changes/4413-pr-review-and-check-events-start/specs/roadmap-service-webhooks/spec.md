## ADDED Requirements

### Requirement: The consumer takes the pull request, review and check events
The event set of the roadmap consumer, `CONST_ROADMAP_WEBHOOK_EVENTS`, SHALL hold `issues`, `pull_request`, `pull_request_review` and `check_suite`, and step 8 of the roadmap-service runbook, `docs/CLUSTER.md`, SHALL name the same events.

#### Scenario: The event set holds the pull, review and check events
- **WHEN** a test reads `CONST_ROADMAP_WEBHOOK_EVENTS`
- **THEN** the set holds `issues`, `pull_request`, `pull_request_review` and `check_suite`

#### Scenario: The runbook step and the event set name the same events
- **WHEN** a test reads `CONST_ROADMAP_WEBHOOK_EVENTS` and step 8 of `docs/CLUSTER.md`
- **THEN** each event of the set is named in that step

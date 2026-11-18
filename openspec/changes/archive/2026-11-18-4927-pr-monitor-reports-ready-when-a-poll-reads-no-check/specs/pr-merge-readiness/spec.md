## ADDED Requirements

### Requirement: A payload with no head commit fails closed
`assess_merge_readiness` SHALL hold a `checks_unread` blocker when the pull request payload gives no head commit SHA, and SHALL NOT report the pull request ready. `devops pr monitor` SHALL report such a poll as not ready, with `checks_failed` set and exit code 1.

#### Scenario: Payload with no head SHA
- **WHEN** the payload of the pull request holds no `head.sha`
- **THEN** the verdict holds `BlockerKind.CHECKS_UNREAD`, `is_ready` is False, and the first blocker text starts with `PR #<n> check verification failed closed:`

#### Scenario: Monitor poll with no head SHA
- **WHEN** `get_pr_monitoring_status` reads a pull request payload with no `head.sha`
- **THEN** the status holds `checks_failed` True and a non-empty `blockers`, and the settled result holds `success` False and `exit_code` 1

## MODIFIED Requirements

### Requirement: The watch row marks a delivery draft ready only after a fix
For a delivery draft with the verdict READY, the watch row SHALL run the ready path of the step `fix-checks` only when its item records `fix_checks.result` as `repaired`, once for each head, with `--confirm` only in mode `on` of `roadmap.fix_checks.mode`, and SHALL ask the step for its ready path only. The row SHALL leave each other delivery draft to its implement Job and SHALL send it no request.

#### Scenario: A repaired draft gets the ready path once
- **WHEN** a delivery draft that a fix Job repaired has passing checks, and the row runs twice on its head in mode `plan`
- **THEN** the row runs the ready path once, with no `--confirm` and with `ready_only`

#### Scenario: A draft that no fix repaired is left alone
- **WHEN** a delivery draft whose implement Job ended has passing checks and no `fix_checks.result`
- **THEN** the row runs no ready path and sends GitHub only its GraphQL read

## ADDED Requirements

### Requirement: An error of the fix-checks round does not stop the watch row
When the fix-checks round raises a Kubernetes error, such as `ClusterJobError`, or a `ConfigurationError`, the watch row SHALL log it, count it in `devops_cli_service_fix_checks_jobs_total` with the result `round_error`, keep its ledger, and give its result with an empty fix-checks round.

#### Scenario: A missing CronJob
- **WHEN** a bot pull request is due for a fix and CronJob `devops-cli-runner` is missing
- **THEN** the row logs and counts `round_error`, writes its ledger, and gives its result

#### Scenario: Limits that do not nest
- **WHEN** a bot pull request is due for a fix and `roadmap.implement.step_time_limit_seconds` gives a deadline above the cap
- **THEN** the row logs and counts `round_error`, writes its ledger, and gives its result

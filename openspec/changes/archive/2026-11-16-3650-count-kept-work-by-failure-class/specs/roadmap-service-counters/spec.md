## MODIFIED Requirements

### Requirement: The Service starts the implement pipeline counters at zero
The Service SHALL create each bounded label set of its implement pipeline counters at zero when it starts. The bounded label sets are: each repository, item class and result on `devops_cli_service_implement_jobs_total`; each repository and item class on `devops_cli_service_implement_repair_rounds_total` and `devops_cli_service_implement_tokens_total`; and each repository, member of `FailureClass` and outcome (`continued`, `finished` or `blocked`) on `devops_cli_service_kept_work_total`.

#### Scenario: A new Service exposes zero counter series
- **WHEN** A Service starts with repository `owner/repo` and item classes `feat` and `fix`.
- **THEN** Each new counter exposes a zero series for each known label set before any runner Job is reported.

#### Scenario: The kept-work series start at zero
- **WHEN** A Service starts with repository `owner/repo`.
- **THEN** The kept-work counter exposes a zero series for each member of `FailureClass` with each of the outcomes `continued`, `finished` and `blocked`, and no series with another outcome.

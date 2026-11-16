## MODIFIED Requirements

### Requirement: The Service starts the implement pipeline counters at zero
The Service SHALL start each label set of its implement pipeline counters at zero: for each repository and item class, `devops_cli_service_implement_jobs_total` SHALL hold the class `none` and each failure class for the result `failed`, the class `none` for `succeeded` and `gone`, and the class `none` or a failure class for `continued`, `finished` and `blocked`; the repair-rounds and token counters SHALL hold each repository and item class.

#### Scenario: A new Service exposes zero counter series
- **WHEN** A Service starts with repository `owner/repo` and item classes `feat` and `fix`.
- **THEN** Each new counter exposes a zero series for each known label set before any runner Job is reported.

#### Scenario: The kept-work series start at zero
- **WHEN** A Service starts with repository `owner/repo` and item classes `feat` and `fix`.
- **THEN** The jobs counter exposes a zero series for the results `succeeded` and `gone` with the class `none`, for the result `failed` with `none` and with each of the 21 failure classes, and for the results `continued`, `finished` and `blocked` with `none` and with each of the 21 failure classes.

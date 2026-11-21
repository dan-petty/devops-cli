## ADDED Requirements

### Requirement: The Service starts the implement Job counters at zero
The Service SHALL create each bounded label set of its implement pipeline counters at zero when it starts. The bounded label sets are: each repository, item class and result on `devops_cli_service_implement_jobs_total`; each repository and item class on `devops_cli_service_implement_repair_rounds_total` and `devops_cli_service_implement_tokens_total`.

#### Scenario: A new Service exposes zero counter series
- **WHEN** A Service starts with repository `owner/repo` and item classes `feat` and `fix`.
- **THEN** Each new counter exposes a zero series for each known label set before any runner Job is reported.

## REMOVED Requirements

### Requirement: The Service starts the implement pipeline counters at zero
**Reason**: The implement Job makes no work-in-progress commit and no work-in-progress push (#6559).
**Migration**: The requirement "The Service starts the implement Job counters at zero" holds the rule.

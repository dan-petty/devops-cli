# Spec Delta

## MODIFIED Requirements

### Requirement: The Service starts each label set of its counters at zero
The Service SHALL create each bounded label set of its counters at zero when it starts. The bounded label sets are: each failure class for each repository of `service.repos` on `devops_cli_service_implement_failures_total`; each repository, lane, row and result on `devops_cli_service_jobs_total`; each repository and lane on `devops_cli_service_job_seconds_total`; and each provider, declared event or `other`, and outcome on `devops_cli_service_webhook_deliveries_total`.

## ADDED Requirements

### Requirement: The Service starts the implement pipeline counters at zero
The Service SHALL create each bounded label set of its implement pipeline counters at zero when it starts. The bounded label sets are: each repository, item class and result on `devops_cli_service_implement_jobs_total`; and each repository and item class on `devops_cli_service_implement_repair_rounds_total` and `devops_cli_service_implement_tokens_total`.

#### Scenario: A new Service exposes zero counter series
- **WHEN** A Service starts with repository `owner/repo` and item classes `feat` and `fix`.
- **THEN** Each new counter exposes a zero series for each known label set before any runner Job is reported.

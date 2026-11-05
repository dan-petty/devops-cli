# roadmap-service-counters Specification

## Purpose
The label sets of the Service counters that the Service creates at zero when it starts, the labels that the job counter and the failure counter carry, and the promtool cases that prove the alerts and the true total over a pod change. A count of a label set that starts at zero is not lost to increase().

## Requirements

### Requirement: The Service starts each label set of its counters at zero
The Service SHALL create each bounded label set of its counters at zero when it starts. The bounded label sets are: each failure class for each repository of `service.repos` on `devops_cli_service_implement_failures_total`; each repository, lane, row and result on `devops_cli_service_jobs_total`; each repository and lane on `devops_cli_service_job_seconds_total`; and each provider, declared event or `other`, and outcome on `devops_cli_service_webhook_deliveries_total`.

#### Scenario: The failure counter exists at zero after start
- **WHEN** the Service starts with the repositories `example/app` and `example/tools`
- **THEN** the failure counter exists at 0 for each of the 19 failure classes and each of the two repositories

#### Scenario: The label repo holds only configured repositories
- **WHEN** the Service starts with the repositories `example/app` and `example/tools`
- **THEN** every value of the label `repo` of the failure counter is `example/app` or `example/tools`

#### Scenario: The webhook counter exists at zero for each declared event
- **WHEN** the Service starts with a provider that declares the events `issues` and `push`
- **THEN** the webhook counter exists at 0 for each of the outcomes with the events `issues`, `push` and `other`

### Requirement: The job counter carries the row of the job
The Service SHALL add 1 to `devops_cli_service_jobs_total` with the labels `repo`, `lane`, `row` and `result` for each row of a lane that ends in the roadmap run. A scoped update SHALL add 1 with the name of its job as the label `row`. The Service SHALL NOT count a lane batch as one job.

#### Scenario: A row that succeeds
- **WHEN** the status lane runs the row `metrics` for `example/app` and the row succeeds
- **THEN** the job counter for `repo` `example/app`, `lane` `status`, `row` `metrics` and `result` `success` grows by 1

#### Scenario: Two rows of one batch
- **WHEN** one round of the status lane runs the rows `metrics` and `implement`, and both fail
- **THEN** the job counter for each row with `result` `error` grows by 1, and no series counts the batch

### Requirement: Alerts read a counter that starts at zero with increase
The alerts `RoadmapServiceWebhooksRejected` and `RoadmapServiceSelfDeliveriesHigh` SHALL read their counter with `increase()` and no `offset` term, because the Service starts each label set at zero.

#### Scenario: A rejected burst on a new pod
- **WHEN** `promtool test rules` evaluates the rejected series of a pod that starts at 0 and reaches 25 within 15 minutes
- **THEN** `RoadmapServiceWebhooksRejected` fires

### Requirement: A query gives the true total over a pod change
A query of `sum(increase(devops_cli_service_implement_failures_total[24h]))` SHALL give the true total of the counts of all pods in the window, including the counts of a pod that started during the window.

#### Scenario: A new pod adds its counts
- **WHEN** `promtool test rules` evaluates the failure counter of a pod that counted 3 and of a new pod that counted 2 after a zero sample at its start
- **THEN** the sum of `increase()` over the window is 5

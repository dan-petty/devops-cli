# roadmap-service-counters Specification

## Purpose
The label sets of the counters of the roadmap Service, which the Service creates at zero when it starts, the labels that these counters carry, and the alerts that read them.

## Requirements

### Requirement: The Service starts each label set of its counters at zero
The Service SHALL create each bounded label set of its counters at zero when it starts. The bounded label sets are: each failure class for each repository of `service.repos` on `devops_cli_service_implement_failures_total`; each repository, lane, row and result on `devops_cli_service_jobs_total`; each repository and lane on `devops_cli_service_job_seconds_total`; each provider, declared event or `other`, and outcome on `devops_cli_service_webhook_deliveries_total`.

#### Scenario: The failure counter exists at zero after start
- **WHEN** the Service starts with the repositories `example/app` and `example/tools`
- **THEN** the failure counter exists at 0 for each of the 18 failure classes and each of the two repositories

#### Scenario: The label repo holds only configured repositories
- **WHEN** the Service starts with the repositories `example/app` and `example/tools`
- **THEN** every value of the label `repo` of the failure counter is `example/app` or `example/tools`

#### Scenario: The webhook counter exists at zero for each declared event
- **WHEN** the Service starts with a provider that declares the events `issues` and `push`
- **THEN** the webhook counter exists at 0 for each of the outcomes with the events `issues`, `push` and `other`

### Requirement: The Service starts the trigger and chat counters at zero
The Service SHALL create each bounded label set of `devops_cli_service_triggers_total` and `devops_cli_service_chat_commands_total` at zero when it starts. The bounded label sets are: each repository of `service.repos` with each source `webhook` or `poll`; and each result `usage`, `status`, `unknown_repo` or `error` of the `/roadmap` chat command.

#### Scenario: The trigger and chat counters exist at zero after start
- **WHEN** the Service starts with the repositories `example/app` and `example/tools`
- **THEN** the trigger counter exists at 0 for each repository with the sources `webhook` and `poll`, and the chat counter exists at 0 for each result `usage`, `status`, `unknown_repo` and `error`

### Requirement: The Service starts the budget hold counter at zero
The Service SHALL create the one series of `devops_cli_service_budget_holds_total` at zero when it starts.

#### Scenario: The budget hold counter exists at zero after start
- **WHEN** the Service starts
- **THEN** the budget hold counter exists at 0 with no label

### Requirement: The job counter carries the row of the job
The Service SHALL add 1 to `devops_cli_service_jobs_total` with the labels `repo`, `lane`, `row` and `result` for each row of a lane that ends in the roadmap run. A scoped update SHALL add 1 with the name of its job as the label `row`. The Service SHALL NOT count a lane batch as one job. The label `result` SHALL be `success`, `error` or `stopped`. A row or a scoped update that the stop of the Service ends SHALL count under `stopped`, and not under `error`.

#### Scenario: A row that succeeds
- **WHEN** the status lane runs the row `metrics` for `example/app` and the row succeeds
- **THEN** the job counter for `repo` `example/app`, `lane` `status`, `row` `metrics` and `result` `success` grows by 1

#### Scenario: Two rows of one batch
- **WHEN** one round of the status lane runs the rows `metrics` and `implement`, and both fail
- **THEN** the job counter for each row with `result` `error` grows by 1, and no series counts the batch

#### Scenario: A row that the stop of the Service ends
- **WHEN** the stop of the Service ends the row `implement` of the status lane
- **THEN** the job counter of that row with `result` `stopped` grows by 1, and the counter with `result` `error` does not change

### Requirement: The job failure alert reads each row
`RoadmapServiceJobsFailing` SHALL group and join on `repo`, `lane` and `row`, so that a success of another row of the lane does not hide a row whose jobs all failed.

#### Scenario: A row fails while another row of its lane succeeds
- **WHEN** `promtool test rules` evaluates a status lane whose row `implement` fails each round and whose row `metrics` succeeds
- **THEN** `RoadmapServiceJobsFailing` fires with the labels `repo`, `lane` `status` and `row` `implement`

### Requirement: Alerts read a counter that starts at zero with increase
The alerts `RoadmapServiceWebhooksRejected` and `RoadmapServiceSelfDeliveriesHigh` SHALL read their counter with `increase()` and no `offset` term, because the Service starts each label set at zero.

#### Scenario: A rejected burst on a new pod
- **WHEN** `promtool test rules` evaluates the rejected series of a pod that starts at 0 and reaches 25 within 15 minutes
- **THEN** `RoadmapServiceWebhooksRejected` fires

### Requirement: A query gives the true total over a pod change
A query of `sum(increase(devops_cli_service_implement_failures_total[1h]))` SHALL give the counts of all pods in the window, including the counts of a pod that started during the window. The only difference from the counts SHALL be the extrapolation of `increase()` to the window edges.

#### Scenario: A new pod adds its counts
- **WHEN** `promtool test rules` evaluates the failure counter of a pod that counted 3 and of a new pod that counted 2 after a zero sample at its start
- **THEN** the sum of `increase()` over the window is the 5 counts plus the extrapolation to the window edges, about 5.03

### Requirement: The devops-cli dashboard charts the series of the Service
The dashboard `k8s/monitoring/dashboards/devops-cli.json` SHALL have the row "Roadmap Service". The panels of the row SHALL read each `devops_cli_service_*` series that `src/devops_cli/config/constants.py` names.

#### Scenario: Each series has a panel
- **WHEN** the queries of the row "Roadmap Service" are read
- **THEN** each `CONST_SERVICE_METRIC_*` series is in a query of the row

#### Scenario: The budget panel shows the spend beside the limit
- **WHEN** the panel "Service GitHub Budget" is read
- **THEN** it has one query for `devops_cli_service_budget_spent_requests` and one for `devops_cli_service_budget_limit_requests`

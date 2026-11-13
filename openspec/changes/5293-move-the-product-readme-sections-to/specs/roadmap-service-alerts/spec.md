## MODIFIED Requirements

### Requirement: Each alert points to its runbook step

Each description in the group SHALL end with `(docs/CLUSTER.md, Roadmap service)`, and that section SHALL say what to do for each alert.

#### Scenario: The README section

- **WHEN** a test reads the descriptions and "Roadmap service" in `docs/CLUSTER.md`
- **THEN** each description points to the section, and the section names each alert

### Requirement: The webhook route has its own alert group
The rule group `roadmap-service-webhooks` in `k8s/monitoring/prometheus-values.yaml`, separate from the group `roadmap-service`, SHALL hold the warning alert `RoadmapServiceWebhooksRejected`. Its description SHALL end with `(docs/CLUSTER.md, Roadmap service)`, and that section SHALL name the alert.

#### Scenario: The rule names the Service
- **WHEN** a test reads the selectors of the group
- **THEN** each selector of `devops_cli_service_webhook_deliveries_total` has `job="roadmap-service"` and `outcome="rejected"`

#### Scenario: The README section
- **WHEN** a test reads the description of the alert and "Roadmap service" in `docs/CLUSTER.md`
- **THEN** the description points to the section, and the section names the alert

### Requirement: The Service's activity has its own alert group
The rule group `roadmap-service-activity` in `k8s/monitoring/prometheus-values.yaml`, apart from the group `roadmap-service`, SHALL hold the warning alerts `RoadmapServiceGitHubWritesHigh`, `RoadmapServiceSelfDeliveriesHigh`, `RoadmapServiceWebSearchRefused` and `RoadmapServiceAlternativesNotSearching`. promtool SHALL accept them. Each SHALL select only the Service's job and point to the section "Roadmap service" of `docs/CLUSTER.md`.

#### Scenario: The selectors of the group
- **WHEN** a test reads the selectors of the group
- **THEN** each `devops_cli_` selector has `job="roadmap-service"`

### Requirement: The item ages have their own alert group
The rule group `roadmap-service-items` in `k8s/monitoring/prometheus-values.yaml` SHALL hold the warning alert `RoadmapServiceItemStuck`. promtool SHALL accept it. Each `devops_cli_` selector of the group SHALL have `job="roadmap-service"`. The description SHALL point to the section "Roadmap service" of `docs/CLUSTER.md`. That section SHALL say what to do.

#### Scenario: The selectors of the group
- **WHEN** a test reads the selectors of the group
- **THEN** each `devops_cli_` selector has `job="roadmap-service"` and names a series that the Service sends

### Requirement: The planner tools have their own alert group
The rule group `roadmap-service-tools` in `k8s/monitoring/prometheus-values.yaml`, apart from the other groups of the Service, SHALL hold the warning alert `RoadmapServiceToolUnused`. Each `devops_cli_` selector of the group SHALL have `job="roadmap-service"`. Its description SHALL end with `(docs/CLUSTER.md, Roadmap service)`, and that section SHALL name the alert. promtool SHALL accept the rule.

#### Scenario: The selectors of the group
- **WHEN** a test reads the selectors of the group
- **THEN** each `devops_cli_` selector has `job="roadmap-service"`

#### Scenario: The README section
- **WHEN** a test reads the description of the alert and "Roadmap service" in `docs/CLUSTER.md`
- **THEN** the description points to the section, and the section names the alert

### Requirement: A state record that stays unwritten warns
`RoadmapServiceStateUnkept` SHALL be an alert of the group `roadmap-service` with warning severity. It SHALL fire after 15 minutes while `devops_cli_service_state_unkept` of the job `roadmap-service` is above 0 for a `record`, and its summary and description SHALL name the record. Its description SHALL end with `(docs/CLUSTER.md, Roadmap service)`, and that section SHALL name the alert and say what to check.

#### Scenario: A record that stays unwritten
- **WHEN** `promtool test rules` evaluates the gauge of the record `ledger` at 1 for more than 15 minutes
- **THEN** `RoadmapServiceStateUnkept` fires with the record `ledger`, and it is quiet before the 15 minutes pass

#### Scenario: A record that is written again
- **WHEN** `promtool test rules` evaluates the gauge of a record at 1 for 10 minutes, then at 0
- **THEN** `RoadmapServiceStateUnkept` stays quiet

#### Scenario: A series of another job
- **WHEN** `promtool test rules` evaluates the gauge with `job="devops-cli"` or `job="kubernetes-pods"` at 1
- **THEN** no alert counts it

### Requirement: The memory alert warns before the limit
The rule group `roadmap-service` SHALL hold the warning alert `RoadmapServiceMemoryNearLimit`. It SHALL fire after 10 minutes when the working set of container `service` of a pod `roadmap-service-.+` in namespace `devops` is above 85% of the memory limit of that container. Its description SHALL end with `(docs/CLUSTER.md, Roadmap service)`, and that section SHALL name the alert and say what to do.

#### Scenario: The working set stays above 85% of the limit
- **WHEN** `promtool test rules` evaluates a working set at 90% of the limit for 20 minutes
- **THEN** `RoadmapServiceMemoryNearLimit` fires with the pod, and it does not fire at the 12th minute, before the wait ends.

#### Scenario: Another namespace or container
- **WHEN** `promtool test rules` evaluates a working set at 99% of the limit for another container of the pod, or for a pod of another namespace
- **THEN** no alert fires for it.

### Requirement: A row that stays suspended warns
`RoadmapServiceRowSuspended` SHALL be an alert of the group `roadmap-service` with warning severity. It SHALL fire after 3 hours while `devops_cli_service_job_suspended` of the job `roadmap-service` is above 0 for a `repo`, a `row` and a `class`, and its summary and description SHALL name the row, the repository and the class. Its description SHALL end with `(docs/CLUSTER.md, Roadmap service)`, and that section SHALL name the alert and say what to check.

#### Scenario: A row that stays suspended
- **WHEN** `promtool test rules` evaluates the gauge of the row `intake` with `class="provider"` at 1 for more than 3 hours
- **THEN** `RoadmapServiceRowSuspended` fires with the repository, the row and the class, and it is quiet before the 3 hours pass

#### Scenario: A row that runs again
- **WHEN** `promtool test rules` evaluates the gauge of a row at 1 for 1 hour, then at 0
- **THEN** `RoadmapServiceRowSuspended` stays quiet

#### Scenario: A class that changes
- **WHEN** `promtool test rules` evaluates the gauge of a row with `class="provider"` at 1 for 1 hour, then with `class="ci_infra"` at 1 for 4 hours
- **THEN** `RoadmapServiceRowSuspended` fires with `class="ci_infra"` only

#### Scenario: A series of another job
- **WHEN** `promtool test rules` evaluates the gauge with `job="devops-cli"` or `job="kubernetes-pods"` at 1
- **THEN** no alert counts it

### Requirement: Failed deliveries of the hooks warn
The rule group `roadmap-service-webhooks` SHALL hold the warning alert `RoadmapServiceWebhookDeliveriesFailed`. It SHALL fire when `devops_cli_service_webhook_delivery_failures` of the job `roadmap-service`, added by `repo`, is more than 5. Its summary and its description SHALL name the repository, and its description SHALL end with `(docs/CLUSTER.md, Roadmap service)`. It SHALL NOT count the series of another job.

#### Scenario: More than 5 failed deliveries of one repository
- **WHEN** `promtool test rules` evaluates 5 failed deliveries of one repository, then 6
- **THEN** `RoadmapServiceWebhookDeliveriesFailed` stays quiet at 5, and fires at 6 with the label `repo` of that repository

#### Scenario: Another repository and another job
- **WHEN** `promtool test rules` evaluates 3 failed deliveries of another repository, and 20 of the job `devops-cli`
- **THEN** `RoadmapServiceWebhookDeliveriesFailed` does not fire for them

#### Scenario: The refusals end
- **WHEN** the gauge goes from 8 to 0
- **THEN** `RoadmapServiceWebhookDeliveriesFailed` stops

## ADDED Requirements

### Requirement: The metrics row counts the failed deliveries of the hooks
Each time the metrics row of the Service runs, it SHALL read the active hooks of its repository and the newest 100 deliveries of each active hook through `gh api`, so that the request budget of the Service counts each read. It SHALL set the gauge `devops_cli_service_webhook_delivery_failures` by `repo` and `code` to the deliveries of the last 15 minutes whose status code is not 2xx.

#### Scenario: Two refusals in the window
- **WHEN** the newest page of deliveries of the hook holds two 403 answers of the last 15 minutes, one 202 answer and one 403 answer from before the 15 minutes
- **THEN** the gauge of code `403` is 2, the read sends one request for the hooks and one for the deliveries of the hook

#### Scenario: Two hooks and an inactive hook
- **WHEN** two active hooks have failed deliveries with the codes 403, 502 and 504, and an inactive hook has a 403
- **THEN** the gauge adds the deliveries of the two active hooks by code, and the inactive hook gets no request

### Requirement: The gauge of failed deliveries follows the last read
A code that the last read of the repository set and this read does not find SHALL go to 0. A read that fails SHALL fail the row and SHALL leave the gauge at the value of the last read.

#### Scenario: The refusals end
- **WHEN** a read sets the code `403` to 2, and the next read finds no failed delivery
- **THEN** the gauge of code `403` is 0

#### Scenario: A refused read
- **WHEN** GitHub refuses the read of the hooks
- **THEN** the read raises `GitHubOperationError`, and the gauge keeps the value of the last read

### Requirement: The installation token reads the hooks
Each installation token of the App SHALL ask for `repository_hooks: read` with the permissions of the roadmap jobs.

#### Scenario: The token asks for the hooks
- **WHEN** the process mints an installation token of the App
- **THEN** the token request asks for `repository_hooks: read` with the permissions of the roadmap jobs

### Requirement: Failed deliveries of the hooks warn
The rule group `roadmap-service-webhooks` SHALL hold the warning alert `RoadmapServiceWebhookDeliveriesFailed`. It SHALL fire when `devops_cli_service_webhook_delivery_failures` of the job `roadmap-service`, added by `repo`, is more than 5. Its summary and its description SHALL name the repository, and its description SHALL end with `(k8s/README.md, Roadmap service)`. It SHALL NOT count the series of another job.

#### Scenario: More than 5 failed deliveries of one repository
- **WHEN** `promtool test rules` evaluates 5 failed deliveries of one repository, then 6
- **THEN** `RoadmapServiceWebhookDeliveriesFailed` stays quiet at 5, and fires at 6 with the label `repo` of that repository

#### Scenario: Another repository and another job
- **WHEN** `promtool test rules` evaluates 3 failed deliveries of another repository, and 20 of the job `devops-cli`
- **THEN** `RoadmapServiceWebhookDeliveriesFailed` does not fire for them

#### Scenario: The refusals end
- **WHEN** the gauge goes from 8 to 0
- **THEN** `RoadmapServiceWebhookDeliveriesFailed` stops

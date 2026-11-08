## ADDED Requirements

### Requirement: A row that stays suspended warns
`RoadmapServiceRowSuspended` SHALL be an alert of the group `roadmap-service` with warning severity. It SHALL fire after 3 hours while `devops_cli_service_job_suspended` of the job `roadmap-service` is above 0 for a `repo`, a `row` and a `class`, and its summary and description SHALL name the row, the repository and the class. Its description SHALL end with `(k8s/README.md, Roadmap service)`, and that section SHALL name the alert and say what to check.

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

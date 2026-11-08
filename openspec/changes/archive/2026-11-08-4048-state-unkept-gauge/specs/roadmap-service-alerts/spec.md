## ADDED Requirements

### Requirement: A state record that stays unwritten warns
`RoadmapServiceStateUnkept` SHALL be an alert of the group `roadmap-service` with warning severity. It SHALL fire after 15 minutes while `devops_cli_service_state_unkept` of the job `roadmap-service` is above 0 for a `record`, and its summary and description SHALL name the record. Its description SHALL end with `(k8s/README.md, Roadmap service)`, and that section SHALL name the alert and say what to check.

#### Scenario: A record that stays unwritten
- **WHEN** `promtool test rules` evaluates the gauge of the record `ledger` at 1 for more than 15 minutes
- **THEN** `RoadmapServiceStateUnkept` fires with the record `ledger`, and it is quiet before the 15 minutes pass

#### Scenario: A record that is written again
- **WHEN** `promtool test rules` evaluates the gauge of a record at 1 for 10 minutes, then at 0
- **THEN** `RoadmapServiceStateUnkept` stays quiet

#### Scenario: A series of another job
- **WHEN** `promtool test rules` evaluates the gauge with `job="devops-cli"` or `job="kubernetes-pods"` at 1
- **THEN** no alert counts it

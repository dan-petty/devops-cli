## ADDED Requirements

### Requirement: A spent provider key is critical
`RoadmapProviderKeySpendLimit` SHALL be an alert of the group `roadmap-service` with critical severity and no wait. It SHALL fire for a `repo` while, for the job `roadmap-service` and the class `spend_limit`, `devops_cli_service_stage_jobs_total` with `result="failed"` or `devops_cli_service_implement_failures_total` increased in the last hour, or `devops_cli_service_job_suspended` is above 0.

#### Scenario: A stage Job on a spent key
- **WHEN** `promtool test rules` evaluates a stage Job counter of `example/app` with `result="failed"` and `class="spend_limit"` that increases by 1
- **THEN** `RoadmapProviderKeySpendLimit` fires with the repository at once, and stops 1 hour after the increase

#### Scenario: An implement Job or a suspended row on a spent key
- **WHEN** `promtool test rules` evaluates the implement failure counter with `class="spend_limit"` that increases by 1, or the suspended gauge of the row `refine` with `class="spend_limit"` at 1
- **THEN** `RoadmapProviderKeySpendLimit` fires with the repository

#### Scenario: Another class
- **WHEN** `promtool test rules` evaluates the same series with `class="provider"` or `class="ci_infra"`
- **THEN** `RoadmapProviderKeySpendLimit` stays quiet

#### Scenario: A series of another job
- **WHEN** `promtool test rules` evaluates the series with `class="spend_limit"` and `job="devops-cli"`
- **THEN** no alert counts it

### Requirement: The spend-limit alert names the person step
The summary of `RoadmapProviderKeySpendLimit` SHALL name the spend limit and the repository. Its description SHALL name the person step: raise the spend limit of the provider key, or change the key in the gateway. It SHALL end with `(docs/CLUSTER.md, Roadmap service)`, and that section SHALL name the alert and say what to check. `RoadmapServiceJobsFailing` SHALL NOT change.

#### Scenario: The text of the alert
- **WHEN** `promtool test rules` evaluates the alert for `example/app`
- **THEN** its summary names the spend limit and `example/app`, and its description names the person step and ends with `(docs/CLUSTER.md, Roadmap service)`

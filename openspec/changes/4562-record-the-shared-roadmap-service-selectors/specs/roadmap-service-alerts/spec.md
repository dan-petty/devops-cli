## MODIFIED Requirements

### Requirement: A row that stays suspended warns
`RoadmapServiceRowSuspended` SHALL be an alert of the group `roadmap-service` with warning severity. It SHALL fire after 3 hours while `repo_row_class:devops_cli_service_job_suspended:max` of the group `roadmap-service-recording` is above 0 for a `repo`, a `row` and a `class`, and its summary and description SHALL name the row, the repository and the class. Its description SHALL end with `(docs/CLUSTER.md, Roadmap service)`, and that section SHALL name the alert and say what to check.

#### Scenario: A row that stays suspended
- **WHEN** `promtool test rules` evaluates the recorded gauge of the row `intake` with `class="provider"` at 1 for more than 3 hours
- **THEN** `RoadmapServiceRowSuspended` fires with the repository, the row and the class, and it is quiet before the 3 hours pass

#### Scenario: A row that runs again
- **WHEN** `promtool test rules` evaluates the recorded gauge of a row at 1 for 1 hour, then at 0
- **THEN** `RoadmapServiceRowSuspended` stays quiet

#### Scenario: A class that changes
- **WHEN** `promtool test rules` evaluates the recorded gauge of a row with `class="provider"` at 1 for 1 hour, then with `class="ci_infra"` at 1 for 4 hours
- **THEN** `RoadmapServiceRowSuspended` fires with `class="ci_infra"` only

#### Scenario: A series of another job
- **WHEN** `promtool test rules` evaluates the gauge with `job="devops-cli"` or `job="kubernetes-pods"` at 1 in the case file of `roadmap-service-recording`
- **THEN** the recorded series is absent and no alert counts it

### Requirement: Failed jobs and a stalled lane warn
`RoadmapServiceJobsFailing` SHALL fire with warning severity after 30 minutes when `repo_lane_row:devops_cli_service_jobs_total:increase1h` of the group `roadmap-service-recording` is above 0 for `result="error"` with no `result="success"` series of the same `repo`, `lane` and `row`. Its summary SHALL name the repository, the lane and the row. `RoadmapServiceLaneStalled` SHALL fire after 10 minutes when no job started for 2 hours while a replica is available.

#### Scenario: A lane whose new error series reaches 3
- **WHEN** `promtool test rules` evaluates a recorded error series of one repository, lane and row that reaches 3 in the hour with no recorded success
- **THEN** `RoadmapServiceJobsFailing` fires with that repository, lane and row after 30 minutes

#### Scenario: A new error series with one sample
- **WHEN** `promtool test rules` evaluates a recorded error series with one sample of 3 and no recorded success
- **THEN** `RoadmapServiceJobsFailing` fires after 30 minutes

#### Scenario: A sparse error series from before the hour
- **WHEN** `promtool test rules` evaluates a recorded error series with samples 5, 6 and 7 at 50, 70 and 110 minutes, at 120 minutes with no recorded success
- **THEN** `RoadmapServiceJobsFailing` fires after 30 minutes

#### Scenario: No available replica
- **WHEN** no job of a lane started for over 2 hours and the deployment has no available replica
- **THEN** `RoadmapServiceLaneStalled` stays quiet

#### Scenario: A worker starts
- **WHEN** a worker of a lane starts and has started no job
- **THEN** the job start gauge of its repository and lane holds the time that the worker started

#### Scenario: A lane of a new pod that starts no job
- **WHEN** `promtool test rules` evaluates the job start of the old pod, which stops, and the job start of the new pod at the start of its worker, with an available replica
- **THEN** `RoadmapServiceLaneStalled` fires with the repository and lane once more than 2 hours and 10 minutes passed since the worker started

### Requirement: A high request volume warns
`RoadmapServiceGitHubRequestsHigh` SHALL fire when `service:devops_cli_service_budget_requests_per_limit:ratio` of the group `roadmap-service-recording` is above 0.9, and its summary SHALL give the share of the hourly GitHub budget that the Service used, as a percentage. `RoadmapServiceModelRequestsHigh` SHALL fire above 352 model requests in 1 hour that the cache did not answer, SHALL count the first value of a new series, and SHALL NOT count a series from before the hour.

#### Scenario: 600 GitHub requests in an hour
- **WHEN** `promtool test rules` evaluates the recorded budget ratio at 1.2
- **THEN** `RoadmapServiceGitHubRequestsHigh` fires, and the summary gives 120% of the budget

#### Scenario: 400 GitHub requests in an hour with a limit of 500
- **WHEN** `promtool test rules` evaluates the recorded budget ratio at 0.8
- **THEN** `RoadmapServiceGitHubRequestsHigh` stays quiet

#### Scenario: 900 GitHub requests in an hour with a limit of 2000
- **WHEN** `promtool test rules` evaluates the recorded budget ratio at 0.45
- **THEN** `RoadmapServiceGitHubRequestsHigh` stays quiet

#### Scenario: 1900 GitHub requests in an hour with a limit of 2000
- **WHEN** `promtool test rules` evaluates the recorded budget ratio at 0.95
- **THEN** `RoadmapServiceGitHubRequestsHigh` fires, and the summary gives 95% of the budget

#### Scenario: A GitHub request stream that starts in the hour
- **WHEN** `promtool test rules` evaluates the recorded budget ratio of a new stream, whose first sample is 0.6 and that rises to 1.04
- **THEN** `RoadmapServiceGitHubRequestsHigh` fires

#### Scenario: A sparse GitHub request stream from before the hour
- **WHEN** `promtool test rules` evaluates the recorded budget ratio at 0.4, with no sample before the hour
- **THEN** `RoadmapServiceGitHubRequestsHigh` stays quiet

#### Scenario: A model request stream that starts in the hour
- **WHEN** `promtool test rules` evaluates a new stream of model requests that the cache did not answer, whose first sample is 250 and that grows to 415, beside the same stream of cached answers
- **THEN** `RoadmapServiceModelRequestsHigh` fires, and the summary gives 415

#### Scenario: Cached model answers
- **WHEN** the Service sent 300 model requests and the cache answered 600 more in an hour
- **THEN** `RoadmapServiceModelRequestsHigh` stays quiet

#### Scenario: 600 GitHub requests in an hour, 480 of them answered 304
- **WHEN** `promtool test rules` evaluates the recorded budget ratio at 0.24, the share of the 120 requests that GitHub counted
- **THEN** `RoadmapServiceGitHubRequestsHigh` stays quiet

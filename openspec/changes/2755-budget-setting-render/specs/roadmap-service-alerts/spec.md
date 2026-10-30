## MODIFIED Requirements

### Requirement: A high request volume warns

`RoadmapServiceGitHubRequestsHigh` SHALL fire above 90% of the hourly budget that the Service reports in `devops_cli_service_budget_limit_requests`, when the Service sent more GitHub requests than that in 1 hour. It SHALL join the request count and the limit with `on()`, because the two series carry different `instance` labels. `RoadmapServiceModelRequestsHigh` SHALL fire above 352 model requests of the Service in 1 hour that the cache did not answer. Both SHALL count the first value of a series that starts in the hour, and SHALL NOT count the requests of a series from before the hour.

#### Scenario: 600 GitHub requests in an hour

- **WHEN** `promtool test rules` evaluates 600 GitHub requests of the Service in an hour and a reported limit of 500
- **THEN** `RoadmapServiceGitHubRequestsHigh` fires, and the summary gives 600

#### Scenario: 400 GitHub requests in an hour with a limit of 500

- **WHEN** `promtool test rules` evaluates 400 GitHub requests of the Service in an hour and a reported limit of 500
- **THEN** `RoadmapServiceGitHubRequestsHigh` stays quiet

#### Scenario: 900 GitHub requests in an hour with a limit of 2000

- **WHEN** `promtool test rules` evaluates 900 GitHub requests of the Service in an hour and a reported limit of 2000
- **THEN** `RoadmapServiceGitHubRequestsHigh` stays quiet

#### Scenario: 1900 GitHub requests in an hour with a limit of 2000

- **WHEN** `promtool test rules` evaluates 1900 GitHub requests of the Service in an hour and a reported limit of 2000
- **THEN** `RoadmapServiceGitHubRequestsHigh` fires, and the summary gives 1900

#### Scenario: A GitHub request stream that starts in the hour

- **WHEN** `promtool test rules` evaluates a new stream whose first sample is 300 and that grows by 20 every 5 minutes to 520, and a reported limit of 500
- **THEN** `RoadmapServiceGitHubRequestsHigh` fires, and the summary gives 520

#### Scenario: A sparse GitHub request stream from before the hour

- **WHEN** `promtool test rules` evaluates a stream with samples 2000, 2010 and 2020 at 50, 70 and 110 minutes, at 120 minutes, and a reported limit of 500
- **THEN** `RoadmapServiceGitHubRequestsHigh` stays quiet

#### Scenario: A model request stream that starts in the hour

- **WHEN** `promtool test rules` evaluates a new stream of model requests that the cache did not answer, whose first sample is 250 and that grows to 415, beside the same stream of cached answers
- **THEN** `RoadmapServiceModelRequestsHigh` fires, and the summary gives 415

#### Scenario: Cached model answers

- **WHEN** the Service sent 300 model requests and the cache answered 600 more in an hour
- **THEN** `RoadmapServiceModelRequestsHigh` stays quiet

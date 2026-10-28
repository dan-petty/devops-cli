# Spec Delta

## ADDED Requirements

### Requirement: The Service's activity has its own alert group
The rule group `roadmap-service-activity` in `k8s/monitoring/prometheus-values.yaml`, apart from the group `roadmap-service`, SHALL hold the warning alerts `RoadmapServiceGitHubWritesHigh`, `RoadmapServiceSelfDeliveriesHigh` and `RoadmapServiceFirecrawlRefused`. promtool SHALL accept them. Each SHALL select only the Service's job and point to the section "Roadmap service" of `k8s/README.md`.

#### Scenario: The selectors of the group
- **WHEN** a test reads the selectors of the group
- **THEN** each `devops_cli_` selector has `job="roadmap-service"`

### Requirement: A burst of writes or of own deliveries warns
`RoadmapServiceGitHubWritesHigh` SHALL fire above 300 REST requests of the Service in 1 hour that are not a GET. `RoadmapServiceSelfDeliveriesHigh` SHALL fire above 150 deliveries with the outcome `self` in 1 hour. Both SHALL count the first value of a series that starts in the hour.

#### Scenario: 360 writes in an hour
- **WHEN** `promtool test rules` evaluates REST POST and PATCH requests of the Service that add up to 360 in an hour, beside GET, GraphQL and workstation requests
- **THEN** `RoadmapServiceGitHubWritesHigh` fires, and the summary gives 360

#### Scenario: 240 writes in an hour
- **WHEN** `promtool test rules` evaluates 240 REST writes of the Service in an hour
- **THEN** `RoadmapServiceGitHubWritesHigh` stays quiet

#### Scenario: 180 deliveries of the Service's own writes
- **WHEN** `promtool test rules` evaluates 180 deliveries with the outcome `self` in an hour
- **THEN** `RoadmapServiceSelfDeliveriesHigh` fires, and the summary gives 180

### Requirement: A Firecrawl refusal warns
`RoadmapServiceFirecrawlRefused` SHALL fire, by result, when a Firecrawl search of the Service got HTTP 402 or 429 in the last hour, also when its series started in the hour.

#### Scenario: The first Firecrawl 402
- **WHEN** `promtool test rules` evaluates a new series of Firecrawl searches with the result `402` and the value 1
- **THEN** `RoadmapServiceFirecrawlRefused` fires with the result `402`, and stays quiet once an hour passed with no new sample

#### Scenario: An older 402 series with no new refusal
- **WHEN** `promtool test rules` evaluates a 402 series that does not grow in the hour
- **THEN** `RoadmapServiceFirecrawlRefused` stays quiet

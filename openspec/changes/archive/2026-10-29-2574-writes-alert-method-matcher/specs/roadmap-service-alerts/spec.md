## MODIFIED Requirements

### Requirement: A burst of writes or of own deliveries warns
`RoadmapServiceGitHubWritesHigh` SHALL fire above 300 REST writes of the Service in 1 hour: requests with the method `POST`, `PUT`, `PATCH` or `DELETE`. It SHALL name each method that the request classifier calls a REST write, and SHALL NOT count a request whose series has no `method` label. `RoadmapServiceSelfDeliveriesHigh` SHALL fire above 150 deliveries with the outcome `self` in 1 hour. Both SHALL count the first value of a series that starts in the hour.

#### Scenario: 360 writes in an hour
- **WHEN** `promtool test rules` evaluates REST POST and PATCH requests of the Service that add up to 360 in an hour, beside GET, GraphQL and workstation requests
- **THEN** `RoadmapServiceGitHubWritesHigh` fires, and the summary gives 360

#### Scenario: 240 writes in an hour
- **WHEN** `promtool test rules` evaluates 240 REST writes of the Service in an hour
- **THEN** `RoadmapServiceGitHubWritesHigh` stays quiet

#### Scenario: Requests with no method label
- **WHEN** `promtool test rules` evaluates 360 REST requests of the Service in an hour, in a series with no `method` label
- **THEN** `RoadmapServiceGitHubWritesHigh` stays quiet

#### Scenario: The write methods of the rule
- **WHEN** a test reads the method matchers of `RoadmapServiceGitHubWritesHigh`
- **THEN** each one names the methods of `CONST_GH_MUTATION_HTTP_METHODS`, and no other

#### Scenario: 180 deliveries of the Service's own writes
- **WHEN** `promtool test rules` evaluates 180 deliveries with the outcome `self` in an hour
- **THEN** `RoadmapServiceSelfDeliveriesHigh` fires, and the summary gives 180

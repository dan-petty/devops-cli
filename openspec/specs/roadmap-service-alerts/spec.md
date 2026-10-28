# roadmap-service-alerts Specification

## Purpose
Defines the Prometheus alerts that watch the roadmap Service: a refused identity, GitHub throttles, failed jobs, stalled lanes, restarts, an unavailable replica, and the GitHub and model request volume, each over the series of the Service only.

## Requirements

### Requirement: The roadmap Service has its own alert group

The rule group `roadmap-service` in `k8s/monitoring/prometheus-values.yaml` SHALL hold the critical alerts `RoadmapServiceIdentityRefused` and `RoadmapServiceGitHubThrottled`, and the warning alerts `RoadmapServiceJobsFailing`, `RoadmapServiceLaneStalled`, `RoadmapServiceRestarted`, `RoadmapServiceUnavailable`, `RoadmapServiceGitHubRequestsHigh` and `RoadmapServiceModelRequestsHigh`, and promtool SHALL accept them.

#### Scenario: promtool reads the rules

- **WHEN** `promtool check rules` runs over the alert rules of the values file
- **THEN** it accepts each expression and each annotation template

### Requirement: Each selector names the Service

Each selector of a `devops_cli_` series in the group SHALL have `job="roadmap-service"`, and each kube-state-metrics selector SHALL have `namespace="devops"` and the deployment `roadmap-service` or its pods. Each selected series SHALL be one that the code of the Service exports or that the kube-state-metrics of the cluster keeps.

#### Scenario: The selectors of the group

- **WHEN** a test reads the selectors of the group
- **THEN** each `devops_cli_` selector has `job="roadmap-service"`, and each `kube_` selector has `namespace="devops"` and `deployment="roadmap-service"` or `pod=~"roadmap-service-.+"`

#### Scenario: A workstation's series

- **WHEN** `promtool test rules` evaluates the same series with `job="devops-cli"` or `job="kubernetes-pods"`
- **THEN** no alert of the group counts it

### Requirement: Each alert points to its runbook step

Each description in the group SHALL end with `(k8s/README.md, Roadmap service)`, and that section SHALL say what to do for each alert.

#### Scenario: The README section

- **WHEN** a test reads the descriptions and "Roadmap service" in `k8s/README.md`
- **THEN** each description points to the section, and the section names each alert

### Requirement: A refused identity and a throttle are critical

`RoadmapServiceIdentityRefused` SHALL fire while the refusal counter of the Service is above 0. `RoadmapServiceGitHubThrottled` SHALL fire for 15 minutes after one throttle of a GitHub request of the Service.

#### Scenario: A refused identity

- **WHEN** `promtool test rules` evaluates a refusal counter of the Service at 1
- **THEN** `RoadmapServiceIdentityRefused` fires with the identity, and holds while the counter stays at 1

#### Scenario: One throttle

- **WHEN** `promtool test rules` evaluates one throttle sample of the Service
- **THEN** `RoadmapServiceGitHubThrottled` fires with the resource, and stops 15 minutes after the sample

### Requirement: Failed jobs and a stalled lane warn

`RoadmapServiceJobsFailing` SHALL fire when 3 or more jobs of one repository and lane failed in 1 hour, also when the error series of that lane started in the hour, and SHALL NOT count the failures of an error series from before the hour. `RoadmapServiceLaneStalled` SHALL fire after 10 minutes when no job of a repository and lane started for over 2 hours while the deployment has an available replica. In a new pod, the 2 hours SHALL start when the worker of the lane starts.

#### Scenario: A lane whose new error series reaches 3

- **WHEN** `promtool test rules` evaluates a new error series of one repository and lane that reaches 3 in the hour
- **THEN** `RoadmapServiceJobsFailing` fires with that repository and lane, and the summary gives 3

#### Scenario: A new error series with one sample

- **WHEN** `promtool test rules` evaluates a new error series with one sample of 3
- **THEN** `RoadmapServiceJobsFailing` fires, and the summary gives 3

#### Scenario: A sparse error series from before the hour

- **WHEN** `promtool test rules` evaluates an error series with samples 5, 6 and 7 at 50, 70 and 110 minutes, at 120 minutes
- **THEN** `RoadmapServiceJobsFailing` stays quiet

#### Scenario: No available replica

- **WHEN** no job of a lane started for over 2 hours and the deployment has no available replica
- **THEN** `RoadmapServiceLaneStalled` stays quiet

#### Scenario: A worker starts

- **WHEN** a worker of a lane starts and has started no job
- **THEN** the job start gauge of its repository and lane holds the time that the worker started

#### Scenario: A lane of a new pod that starts no job

- **WHEN** `promtool test rules` evaluates the job start of the old pod, which stops, and the job start of the new pod at the start of its worker, with an available replica
- **THEN** `RoadmapServiceLaneStalled` fires with the repository and lane once more than 2 hours and 10 minutes passed since the worker started

### Requirement: Restarts and an unavailable replica warn

`RoadmapServiceRestarted` SHALL fire when the `service` container of the Service restarted in the last hour. `RoadmapServiceUnavailable` SHALL fire when the deployment had an unavailable replica for 10 minutes.

#### Scenario: A restart

- **WHEN** `promtool test rules` evaluates a restart count of the `service` container that increased in the hour
- **THEN** `RoadmapServiceRestarted` fires with the pod

#### Scenario: A rollout

- **WHEN** the deployment has no available replica for 4 minutes
- **THEN** `RoadmapServiceUnavailable` stays quiet

### Requirement: A high request volume warns

`RoadmapServiceGitHubRequestsHigh` SHALL fire above 450 GitHub requests of the Service in 1 hour, 90% of the default hourly budget of 500. `RoadmapServiceModelRequestsHigh` SHALL fire above 352 model requests of the Service in 1 hour that the cache did not answer. Both SHALL count the first value of a series that starts in the hour, and SHALL NOT count the requests of a series from before the hour.

#### Scenario: 600 GitHub requests in an hour

- **WHEN** `promtool test rules` evaluates 600 GitHub requests of the Service in an hour
- **THEN** `RoadmapServiceGitHubRequestsHigh` fires, and the summary gives 600

#### Scenario: A GitHub request stream that starts in the hour

- **WHEN** `promtool test rules` evaluates a new stream whose first sample is 300 and that grows by 20 every 5 minutes to 520
- **THEN** `RoadmapServiceGitHubRequestsHigh` fires, and the summary gives 520

#### Scenario: A sparse GitHub request stream from before the hour

- **WHEN** `promtool test rules` evaluates a stream with samples 2000, 2010 and 2020 at 50, 70 and 110 minutes, at 120 minutes
- **THEN** `RoadmapServiceGitHubRequestsHigh` stays quiet

#### Scenario: A model request stream that starts in the hour

- **WHEN** `promtool test rules` evaluates a new stream of model requests that the cache did not answer, whose first sample is 250 and that grows to 415, beside the same stream of cached answers
- **THEN** `RoadmapServiceModelRequestsHigh` fires, and the summary gives 415

#### Scenario: Cached model answers

- **WHEN** the Service sent 300 model requests and the cache answered 600 more in an hour
- **THEN** `RoadmapServiceModelRequestsHigh` stays quiet

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

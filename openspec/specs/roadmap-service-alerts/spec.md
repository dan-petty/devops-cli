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

`RoadmapServiceJobsFailing` SHALL fire with warning severity after 30 minutes when all jobs of a repository and lane failed in 1 hour (errors increase with zero successes), joined on `repo` and `lane`. Its summary SHALL name the repository and lane, and its description SHALL give a Loki filter. `RoadmapServiceLaneStalled` SHALL fire after 10 minutes when no job started for 2 hours while a replica is available. In a new pod, the 2 hours SHALL start when the worker starts.

#### Scenario: A lane whose new error series reaches 3
- **WHEN** `promtool test rules` evaluates an error series of one repository and lane that reaches 3 in the hour with zero successes
- **THEN** `RoadmapServiceJobsFailing` fires with that repository and lane after 30 minutes

#### Scenario: A new error series with one sample
- **WHEN** `promtool test rules` evaluates a new error series with one sample of 3 and zero successes
- **THEN** `RoadmapServiceJobsFailing` fires after 30 minutes

#### Scenario: A sparse error series from before the hour
- **WHEN** `promtool test rules` evaluates an error series with samples 5, 6 and 7 at 50, 70 and 110 minutes, at 120 minutes with zero successes
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

### Requirement: Restarts and an unavailable replica warn

`RoadmapServiceRestarted` SHALL fire when the `service` container of the Service restarted in the last hour. `RoadmapServiceUnavailable` SHALL fire when the deployment had an unavailable replica for 10 minutes.

#### Scenario: A restart

- **WHEN** `promtool test rules` evaluates a restart count of the `service` container that increased in the hour
- **THEN** `RoadmapServiceRestarted` fires with the pod

#### Scenario: A rollout

- **WHEN** the deployment has no available replica for 4 minutes
- **THEN** `RoadmapServiceUnavailable` stays quiet

### Requirement: A high request volume warns

`RoadmapServiceGitHubRequestsHigh` SHALL fire when the Service sent more GitHub requests in 1 hour, not counting the answers with status 304, than 90% of the budget in `devops_cli_service_budget_limit_requests`, and SHALL join the two with `on()`, because their `instance` labels differ. `RoadmapServiceModelRequestsHigh` SHALL fire above 352 model requests in 1 hour that the cache did not answer. Both SHALL count the first value of a new series, and SHALL NOT count a series from before the hour.

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

#### Scenario: 600 GitHub requests in an hour, 480 of them answered 304

- **WHEN** `promtool test rules` evaluates 120 GitHub requests with status 200 and 480 with status 304 of the Service in an hour and a reported limit of 500
- **THEN** `RoadmapServiceGitHubRequestsHigh` stays quiet

### Requirement: The webhook route has its own alert group
The rule group `roadmap-service-webhooks` in `k8s/monitoring/prometheus-values.yaml`, separate from the group `roadmap-service`, SHALL hold the warning alert `RoadmapServiceWebhooksRejected`. Its description SHALL end with `(k8s/README.md, Roadmap service)`, and that section SHALL name the alert.

#### Scenario: The rule names the Service
- **WHEN** a test reads the selectors of the group
- **THEN** each selector of `devops_cli_service_webhook_deliveries_total` has `job="roadmap-service"` and `outcome="rejected"`

#### Scenario: The README section
- **WHEN** a test reads the description of the alert and "Roadmap service" in `k8s/README.md`
- **THEN** the description points to the section, and the section names the alert

### Requirement: A burst of rejected webhook deliveries warns
`RoadmapServiceWebhooksRejected` SHALL fire when the webhook route of the Service rejected more than 20 deliveries in 15 minutes, also when a series of rejected deliveries started in the 15 minutes. It SHALL NOT count the deliveries of another outcome or of another job.

#### Scenario: A new series of rejected deliveries
- **WHEN** `promtool test rules` evaluates a new series of rejected deliveries that grows by 5 each minute
- **THEN** `RoadmapServiceWebhooksRejected` stays quiet while the series is at 20 or less, and fires when it gets to 25, and the summary gives 25

#### Scenario: A few rejected deliveries of an older series
- **WHEN** `promtool test rules` evaluates a series of rejected deliveries from before the 15 minutes that grows by 1 each minute
- **THEN** `RoadmapServiceWebhooksRejected` stays quiet

#### Scenario: A burst in an older series
- **WHEN** the same series then grows by 3 each minute
- **THEN** `RoadmapServiceWebhooksRejected` fires

#### Scenario: Accepted deliveries and another job
- **WHEN** `promtool test rules` evaluates 10 accepted deliveries of the Service each minute, and 10 rejected deliveries of the job `devops-cli` each minute
- **THEN** `RoadmapServiceWebhooksRejected` stays quiet

### Requirement: The Service's activity has its own alert group
The rule group `roadmap-service-activity` in `k8s/monitoring/prometheus-values.yaml`, apart from the group `roadmap-service`, SHALL hold the warning alerts `RoadmapServiceGitHubWritesHigh`, `RoadmapServiceSelfDeliveriesHigh`, `RoadmapServiceWebSearchRefused` and `RoadmapServiceAlternativesNotSearching`. promtool SHALL accept them. Each SHALL select only the Service's job and point to the section "Roadmap service" of `k8s/README.md`.

#### Scenario: The selectors of the group
- **WHEN** a test reads the selectors of the group
- **THEN** each `devops_cli_` selector has `job="roadmap-service"`

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

### Requirement: A refused web search warns
`RoadmapServiceWebSearchRefused` SHALL fire, by `backend` and `result`, when a search provider of the Service got HTTP 402 or 429 in the last hour in `devops_cli_web_searches_total`, also when its series started in the hour. The summary and the description SHALL name the provider.

#### Scenario: The first Firecrawl 402
- **WHEN** `promtool test rules` evaluates a new series of searches with the backend `firecrawl` and the result `402` and the value 1
- **THEN** `RoadmapServiceWebSearchRefused` fires with the backend `firecrawl` and the result `402`, and stays quiet once an hour passed with no new sample

#### Scenario: A refusal of another provider
- **WHEN** `promtool test rules` evaluates a new series with the backend `duckduckgo` and the result `429`
- **THEN** `RoadmapServiceWebSearchRefused` fires with the backend `duckduckgo`

#### Scenario: An older 402 series with no new refusal
- **WHEN** `promtool test rules` evaluates a 402 series that does not grow in the hour
- **THEN** `RoadmapServiceWebSearchRefused` stays quiet

### Requirement: The item ages have their own alert group
The rule group `roadmap-service-items` in `k8s/monitoring/prometheus-values.yaml` SHALL hold the warning alert `RoadmapServiceItemStuck`. promtool SHALL accept it. Each `devops_cli_` selector of the group SHALL have `job="roadmap-service"`. The description SHALL point to the section "Roadmap service" of `k8s/README.md`. That section SHALL say what to do.

#### Scenario: The selectors of the group
- **WHEN** a test reads the selectors of the group
- **THEN** each `devops_cli_` selector has `job="roadmap-service"` and names a series that the Service sends

### Requirement: A stuck item warns and is named
`RoadmapServiceItemStuck` SHALL fire when `devops_cli_roadmap_item_age_seconds` is above 86400 seconds for `state` `blocked`, or for `state` `ready` with `plan` `true`. Its summary SHALL name the repository, the state and the age. It SHALL also name the item number that `devops_cli_roadmap_oldest_item_number` holds for the same `repo`, `state` and `plan`.

#### Scenario: A Blocked item over a day
- **WHEN** `promtool test rules` evaluates `state` `blocked` with the age 90000 and the number 2919
- **THEN** the alert fires and its summary names item 2919

#### Scenario: A Ready item with a plan
- **WHEN** `promtool test rules` evaluates `state` `ready`, `plan` `true` and the age 90000
- **THEN** the alert fires

#### Scenario: A Ready item with no plan
- **WHEN** `promtool test rules` evaluates `state` `ready`, `plan` `false` and the age 900000
- **THEN** the alert stays quiet

#### Scenario: An item under a day
- **WHEN** `promtool test rules` evaluates `state` `blocked` with the age 80000
- **THEN** the alert stays quiet

#### Scenario: A series of another job
- **WHEN** `promtool test rules` evaluates the same series with `job="devops-cli"`
- **THEN** the alert stays quiet

### Requirement: The planner tools have their own alert group
The rule group `roadmap-service-tools` in `k8s/monitoring/prometheus-values.yaml`, apart from the other groups of the Service, SHALL hold the warning alert `RoadmapServiceToolUnused`. Each `devops_cli_` selector of the group SHALL have `job="roadmap-service"`. Its description SHALL end with `(k8s/README.md, Roadmap service)`, and that section SHALL name the alert. promtool SHALL accept the rule.

#### Scenario: The selectors of the group
- **WHEN** a test reads the selectors of the group
- **THEN** each `devops_cli_` selector has `job="roadmap-service"`

#### Scenario: The README section
- **WHEN** a test reads the description of the alert and "Roadmap service" in `k8s/README.md`
- **THEN** the description points to the section, and the section names the alert

### Requirement: A tool that no run called in 7 days warns
`RoadmapServiceToolUnused` SHALL fire, by `row`, `tool` and `toolset`, when the calls of the tool in 7 days, of all outcomes, are 0, the series of the tool has a sample in the 7 days before that window, and the Service made plan runs of the same `row` and `toolset` in the 7 days. The summary SHALL name the tool and the toolset.

#### Scenario: A tool is not called while runs happen
- **WHEN** `promtool test rules` evaluates a counter that stays at 0 for `repo_map`, a counter that grows for `read_file`, and a histogram of calls per run that grows, all of the same `toolset`
- **THEN** the alert fires for `repo_map` and not for `read_file`

#### Scenario: No run happened
- **WHEN** `promtool test rules` evaluates a counter that stays at 0 for one tool and a histogram of calls per run that does not grow
- **THEN** the alert stays quiet

#### Scenario: A series that starts in the 7 days
- **WHEN** `promtool test rules` evaluates a counter that stays at 0 and starts 90 hours before the evaluation, and a histogram that grows
- **THEN** the alert stays quiet for that tool

#### Scenario: A tool with calls of one outcome
- **WHEN** `promtool test rules` evaluates a counter at 0 with `outcome` `ok` and a counter that grows with `outcome` `error`, for one tool
- **THEN** the alert stays quiet for that tool

#### Scenario: The same tool in the row implement
- **WHEN** `promtool test rules` evaluates the series of a tool and of its runs with `row` `implement`, and the tool has no call
- **THEN** the alert fires with `row` `implement`

#### Scenario: No run series exists
- **WHEN** `promtool test rules` evaluates a counter that stays at 0 for one tool, and no series of calls per run exists
- **THEN** the alert stays quiet

#### Scenario: A tool of another toolset
- **WHEN** `promtool test rules` evaluates a counter at 0 for a tool of the toolset `extended`, and runs of the toolset `base` only
- **THEN** the alert stays quiet for that tool

#### Scenario: A series of another job
- **WHEN** `promtool test rules` evaluates the same series with `job="devops-cli"`
- **THEN** the alert stays quiet

### Requirement: No alternatives search with unchecked items warns
`RoadmapServiceAlternativesNotSearching` SHALL fire, by `repo`, after 1 hour in which the last value of `devops_cli_roadmap_alternatives_unchecked_items` in 7 days is above 0 and the Service has sent no web search in 3 days, of any `backend` and `result`, also when no search series exists. The count of searches SHALL add the first value of a series that starts in the 3 days. The summary SHALL name the repository and the count of items.

#### Scenario: Three days with no search
- **WHEN** `promtool test rules` evaluates a gauge of 2 for `example/app`, a `402` series that does not grow, and no `ok` series
- **THEN** the alert fires with `repo` `example/app`, and the summary names `example/app` and 2 items

#### Scenario: No search series at all
- **WHEN** `promtool test rules` evaluates a gauge of 2 for `example/app` and no search series
- **THEN** the alert fires with `repo` `example/app`

#### Scenario: A search in the window
- **WHEN** `promtool test rules` evaluates a gauge of 2 and an `ok` search 1 day before the evaluation
- **THEN** the alert stays quiet

#### Scenario: A series that starts in the window
- **WHEN** `promtool test rules` evaluates a gauge of 2 and a new `ok` series whose first value is 3, 10 hours before the evaluation
- **THEN** the alert stays quiet

#### Scenario: No unchecked items
- **WHEN** `promtool test rules` evaluates a gauge of 0 and no search series
- **THEN** the alert stays quiet

#### Scenario: A search of another job
- **WHEN** `promtool test rules` evaluates a gauge of 2 for `example/app` and searches of the job `devops-cli` that grow
- **THEN** the alert fires with `repo` `example/app`

#### Scenario: An old gauge
- **WHEN** `promtool test rules` evaluates a gauge whose last sample is 180 hours old, and no search series
- **THEN** the alert stays quiet, and it fires when the last sample is 100 hours old

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

### Requirement: The memory alert warns before the limit
The rule group `roadmap-service` SHALL hold the warning alert `RoadmapServiceMemoryNearLimit`. It SHALL fire after 10 minutes when the working set of container `service` of a pod `roadmap-service-.+` in namespace `devops` is above 85% of the memory limit of that container. Its description SHALL end with `(k8s/README.md, Roadmap service)`, and that section SHALL name the alert and say what to do.

#### Scenario: The working set stays above 85% of the limit
- **WHEN** `promtool test rules` evaluates a working set at 90% of the limit for 20 minutes
- **THEN** `RoadmapServiceMemoryNearLimit` fires with the pod, and it does not fire at the 12th minute, before the wait ends.

#### Scenario: Another namespace or container
- **WHEN** `promtool test rules` evaluates a working set at 99% of the limit for another container of the pod, or for a pod of another namespace
- **THEN** no alert fires for it.

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

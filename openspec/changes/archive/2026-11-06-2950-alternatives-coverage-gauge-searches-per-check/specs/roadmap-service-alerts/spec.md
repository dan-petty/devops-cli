## ADDED Requirements

### Requirement: No alternatives search with unchecked items warns
`RoadmapServiceAlternativesNotSearching` SHALL fire, by `repo`, after 1 hour in which the last value of `devops_cli_roadmap_alternatives_unchecked_items` in 7 days is above 0 and the Service has sent no Firecrawl search in 3 days, of any `result`, also when no search series exists. The count of searches SHALL add the first value of a series that starts in the 3 days. The summary SHALL name the repository and the count of items.

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
- **THEN** the alert fires, since the searches of a workstation do not count

#### Scenario: An old gauge
- **WHEN** `promtool test rules` evaluates a gauge whose last sample is 180 hours old, and no search series
- **THEN** the alert stays quiet, and it fires when the last sample is 100 hours old

## MODIFIED Requirements

### Requirement: The Service's activity has its own alert group
The rule group `roadmap-service-activity` in `k8s/monitoring/prometheus-values.yaml`, apart from the group `roadmap-service`, SHALL hold the warning alerts `RoadmapServiceGitHubWritesHigh`, `RoadmapServiceSelfDeliveriesHigh`, `RoadmapServiceFirecrawlRefused` and `RoadmapServiceAlternativesNotSearching`. promtool SHALL accept them. Each SHALL select only the Service's job and point to the section "Roadmap service" of `k8s/README.md`.

#### Scenario: The selectors of the group
- **WHEN** a test reads the selectors of the group
- **THEN** each `devops_cli_` selector has `job="roadmap-service"`

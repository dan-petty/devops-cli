## ADDED Requirements

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

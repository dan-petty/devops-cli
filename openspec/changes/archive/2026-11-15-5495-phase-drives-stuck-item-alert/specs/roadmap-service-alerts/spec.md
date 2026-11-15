# roadmap-service-alerts Specification

## MODIFIED Requirements

### Requirement: A stuck item warns and is named
`RoadmapServiceItemStuck` SHALL fire when `devops_cli_roadmap_stalled_items` is above 0 for 1 hour. Its summary SHALL name the repository, the phase, and the oldest item number that `devops_cli_roadmap_oldest_item_number` holds for the same `repo` and `phase`.

#### Scenario: A Blocked item over a day
- **WHEN** `promtool test rules` evaluates `devops_cli_roadmap_stalled_items` with a value above 0 for 1 hour
- **THEN** the alert fires and its summary names the item number

#### Scenario: A Ready item with a plan
- **WHEN** `promtool test rules` evaluates stalled items in phase `planned` over 1 hour
- **THEN** the alert fires

#### Scenario: A Ready item with no plan
- **WHEN** `promtool test rules` evaluates stalled items at 0
- **THEN** the alert stays quiet

#### Scenario: An item under a day
- **WHEN** `promtool test rules` evaluates stalled items for under 1 hour
- **THEN** the alert stays quiet

#### Scenario: A series of another job
- **WHEN** `promtool test rules` evaluates the same series with `job="devops-cli"`
- **THEN** the alert stays quiet

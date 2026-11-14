## ADDED Requirements

### Requirement: The dashboard shows the count of each inbox kind
The project dashboard SHALL hold the timeseries panel "Inbox Items by Kind" in the right half of the row of the panel "Oldest Item Age by State", with the unit `short` and one query `sum by (kind) (last_over_time(devops_cli_roadmap_inbox_items[$__range]))` with the legend `{{kind}}`. The panel SHALL pass the dashboard lint of the repository.

#### Scenario: The panel query
- **WHEN** A test reads the panel "Inbox Items by Kind" of `project-metrics.json`
- **THEN** Its query is the one above with the legend `{{kind}}`, its unit is `short`, and no panel of the dashboard overlaps it

## MODIFIED Requirements

### Requirement: The dashboard shows the age of the oldest item in each state
The project dashboard SHALL hold the timeseries panel "Oldest Item Age by State" in the row of the items panels, with the unit `s`. Its queries SHALL be `max by (state) (last_over_time(devops_cli_roadmap_item_age_seconds[$__range]))` and `max(last_over_time(devops_cli_roadmap_claim_age_seconds[$__range]))`. The panel "Inbox Items by Kind" SHALL fill the right half of the same row.

#### Scenario: The queries of the panel
- **WHEN** a test reads the panel "Oldest Item Age by State" of `project-metrics.json`
- **THEN** its two queries are the ones above, each names a declared instrument, and no panel overlaps it

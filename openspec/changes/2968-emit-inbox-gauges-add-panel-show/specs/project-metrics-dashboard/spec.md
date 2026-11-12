## ADDED Requirements

### Requirement: The project dashboard shows the inbox counts
The project dashboard SHALL hold the timeseries panel "Inbox Items by Kind" beside the panel "Oldest Item Age by State", in the right half of its row, with the query `sum by (kind) (last_over_time(devops_cli_roadmap_inbox_items[$__range]))` and the legend `{{kind}}`, and the panel SHALL pass the dashboard lint of the repository.

#### Scenario: The inbox panel passes the dashboard lint
- **WHEN** The dashboard check lints the project dashboard
- **THEN** The check reports no error, and the panel "Inbox Items by Kind" names `devops_cli_roadmap_inbox_items` in its query

#### Scenario: The inbox panel groups only by the kind label
- **WHEN** The query of the panel "Inbox Items by Kind" is read
- **THEN** It groups by `kind` and by no other label

## MODIFIED Requirements

### Requirement: The dashboard shows the age of the oldest item in each state
The project dashboard SHALL hold the timeseries panel "Oldest Item Age by State" in the row of the items panels, with the unit `s`. Its queries SHALL be `max by (state) (last_over_time(devops_cli_roadmap_item_age_seconds[$__range]))` and `max(last_over_time(devops_cli_roadmap_claim_age_seconds[$__range]))`. The panel "Inbox Items by Kind" SHALL fill the right half of the same row.

#### Scenario: The queries of the panel
- **WHEN** a test reads the panel "Oldest Item Age by State" of `project-metrics.json`
- **THEN** its two queries are the ones above, each names a declared instrument, and no panel overlaps it

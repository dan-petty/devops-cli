## ADDED Requirements

### Requirement: Alert on no alternatives search
The alert rules SHALL hold the alert `RoadmapServiceAlternativesNotSearching`, which fires when `increase(devops_cli_firecrawl_searches_total[3d]) == 0` and `devops_cli_roadmap_alternatives_unchecked_items > 0`, and its annotation SHALL name the repository of the gauge.

#### Scenario: Three days with no search and unchecked items
- **WHEN** The promtool unit test feeds no increase of `devops_cli_firecrawl_searches_total` over 3 days and a gauge of 2 for one repository
- **THEN** the alert is in the firing state and its annotation names that repository

#### Scenario: A search in the window
- **WHEN** The promtool unit test feeds an increase of `devops_cli_firecrawl_searches_total` within 3 days and a gauge of 2 for one repository
- **THEN** the alert is not in the firing state

#### Scenario: No unchecked items
- **WHEN** The promtool unit test feeds no increase of `devops_cli_firecrawl_searches_total` over 3 days and a gauge of 0 for one repository
- **THEN** the alert is not in the firing state

## ADDED Requirements

### Requirement: Coverage gauges of a round
The alternatives job SHALL record, at the end of each round and with the attribute `repo`, the gauge `devops_cli_roadmap_alternatives_unchecked_items` with the number of open items that have no check, and the gauge `devops_cli_roadmap_alternatives_oldest_check_age_seconds` with the age in seconds of the oldest check of the repository.

#### Scenario: A repository with unchecked items
- **WHEN** A round finds 10 open items and 4 of them have a check
- **THEN** the gauge `devops_cli_roadmap_alternatives_unchecked_items` records 6 for that repository

#### Scenario: The age of the oldest check
- **WHEN** The oldest check of a repository was written 72 hours before the round
- **THEN** the gauge `devops_cli_roadmap_alternatives_oldest_check_age_seconds` records 259200 for that repository

### Requirement: Searches per check
The alternatives job SHALL record one observation of the histogram `devops_cli_roadmap_alternatives_searches` for each check that it writes, with the attribute `verdict` and the number of Firecrawl searches that the check ran.

#### Scenario: A check that searched three times
- **WHEN** A check of an item runs 3 Firecrawl searches and writes the verdict `none`
- **THEN** the histogram `devops_cli_roadmap_alternatives_searches` records the value 3 with the attribute `verdict` set to `none`

#### Scenario: A check that is skipped
- **WHEN** The job skips an item because a person changed it
- **THEN** the histogram records no observation for that item

## ADDED Requirements

### Requirement: A round records the coverage of the check
The Service row SHALL record, once in each round and before the round writes, the gauge `devops_cli_roadmap_alternatives_unchecked_items` and the gauge `devops_cli_roadmap_alternatives_oldest_check_age_seconds`, with the attribute `repo`. The first counts the items that the check can take (open, Status New or Ready, trusted author) with no check, also one in the retry delay. The second is the age of the oldest check of these items. No other path SHALL record them.

#### Scenario: Six items with no check
- **WHEN** a round finds 10 items that the check can take, 4 of them with a check, and one of the other 6 failed 1 day ago
- **THEN** the gauge `devops_cli_roadmap_alternatives_unchecked_items` records 6 for the repository

#### Scenario: An item that the check cannot take
- **WHEN** an item with no check is In Progress, and another with no check is from an author with no write access
- **THEN** the gauge does not count either of them

#### Scenario: The oldest check is 72 hours old
- **WHEN** the oldest check of the items was written 72 hours before the round
- **THEN** the gauge `devops_cli_roadmap_alternatives_oldest_check_age_seconds` records 259200

#### Scenario: No item has a check
- **WHEN** no item that the check can take has a check
- **THEN** the gauge of the unchecked items records the count, and the gauge of the age records no point

#### Scenario: A round with nothing to check
- **WHEN** every item that the check can take has a current check
- **THEN** the row records the unchecked gauge 0 and the age gauge, and the model gets no request

#### Scenario: A path that is not the Service row
- **WHEN** the command runs with `--item 7`, with no `--confirm`, with `--confirm`, or on a repository where the check is off
- **THEN** neither gauge has a point

### Requirement: Each written check observes its searches
For each check that it writes, the job SHALL observe the histogram `devops_cli_roadmap_alternatives_searches` once, with the attribute `verdict` and the number of searches that the tools of the check ran, also a search that Firecrawl refused. A skip-class check SHALL observe 0. The job SHALL observe nothing for a failed check, for a check skipped because a person changed the body, and for a plan that it does not apply.

#### Scenario: A check that searched three times
- **WHEN** the job writes a check with the verdict `none` after 3 searches
- **THEN** the histogram has the point `{verdict="none"}` with the value 3

#### Scenario: A skip-class check
- **WHEN** the job writes the check of an item titled `docs(roadmap): a change`
- **THEN** the histogram has the point `{verdict="not-applicable"}` with the value 0

#### Scenario: A check that is not written
- **WHEN** a check fails, a person changes the body between the read and the write, or a run only plans
- **THEN** the histogram has no point for that item

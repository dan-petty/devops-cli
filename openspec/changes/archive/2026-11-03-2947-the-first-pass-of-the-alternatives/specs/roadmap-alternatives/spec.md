## MODIFIED Requirements

### Requirement: The limit of a round is a setting
`roadmap.alternatives.limit` (default 5, at least 1) SHALL be the number of items that the row and `devops roadmap alternatives` check in one run when every eligible item has a check. `roadmap.alternatives.first_pass_limit` (default 20, at least 1) SHALL be that number while an eligible item has no check and its last check did not fail inside `roadmap.alternatives.retry_days`. `--limit` SHALL replace either for one run of the command.

#### Scenario: The command without --limit
- **WHEN** `roadmap.alternatives.limit` is 2 and `devops roadmap alternatives` runs without `--limit` on 4 items that have a check older than `roadmap.alternatives.recheck_days`
- **THEN** the plan checks the 2 items with the oldest checks

#### Scenario: The command with --limit
- **WHEN** `roadmap.alternatives.first_pass_limit` is 20 and the command runs with `--limit 3` on 4 unchecked items
- **THEN** the plan checks 3 items

#### Scenario: A first pass
- **WHEN** 25 items have no check, `roadmap.alternatives.limit` is 5 and `roadmap.alternatives.first_pass_limit` is 20
- **THEN** the plan checks the 20 lowest numbers

#### Scenario: Every item has a check
- **WHEN** 8 items have a check older than `roadmap.alternatives.recheck_days`, `roadmap.alternatives.limit` is 5 and `roadmap.alternatives.first_pass_limit` is 20
- **THEN** the plan checks 5 items

#### Scenario: Items with a check join a first pass
- **WHEN** 3 items have no check, 10 items have a check older than `roadmap.alternatives.recheck_days`, and the two limits are 5 and 20
- **THEN** the plan checks the 3 unchecked items and then the 10 with the oldest checks

#### Scenario: A failed item does not hold the first pass
- **WHEN** the only 2 items with no check failed 1 day ago, `roadmap.alternatives.retry_days` is 3, and 8 items have a check older than `roadmap.alternatives.recheck_days`
- **THEN** the plan checks 5 items

### Requirement: The Service runs the check twice a day
The due table of the roadmap SHALL hold the row `alternatives` in `MODEL_LANE_ROWS`, after `refine`. The row SHALL be due on a first run and every `DEFAULT_ROADMAP_ALTERNATIVES_INTERVAL_MINUTES` (719) after its last success, and SHALL be due by no webhook hint. It SHALL check in a round the items that the limit of a round allows, and SHALL fail the round only when it tried items and checked none. `devops roadmap run --dry-run` SHALL list the row when it is due.

#### Scenario: A first run
- **WHEN** a round runs on a roadmap whose `schedule.json` holds no success of the row
- **THEN** the row runs once, after `refine`, with the job's plan and apply functions

#### Scenario: Twice a day
- **WHEN** the row succeeded 2 hours ago and a round runs
- **THEN** the row does not run, and when the row succeeded 13 hours ago it runs

#### Scenario: A webhook hint
- **WHEN** a round runs with a webhook hint that makes intake due and the row succeeded 2 hours ago
- **THEN** the row does not run

#### Scenario: The limit of a round
- **WHEN** `roadmap.alternatives.limit` is 2 and 4 items have a check older than `roadmap.alternatives.recheck_days`
- **THEN** the round checks the 2 items with the oldest checks

#### Scenario: A round of the first pass
- **WHEN** 25 items have no check and the two limits are 5 and 20
- **THEN** the round checks the 20 lowest numbers and writes their checks

#### Scenario: A failed check
- **WHEN** the model call for one item fails and the call for another succeeds
- **THEN** the check of the second item is written, the failure of the first is recorded, and the row succeeds

#### Scenario: Every check fails
- **WHEN** the model call for each of 2 items fails
- **THEN** the failure of each item is recorded and the row fails, naming both

#### Scenario: A round with no item to check
- **WHEN** every eligible item has a current check or a failure inside its delay
- **THEN** the row makes no model call and succeeds

#### Scenario: A dry run lists the row
- **WHEN** `devops roadmap run --dry-run` runs on a roadmap whose rows are all due
- **THEN** its `Due:` line ends with `alternatives`, after `refine`

## ADDED Requirements

### Requirement: The Service runs the check once a day
The due table of the roadmap SHALL hold the row `alternatives` in `MODEL_LANE_ROWS`, after `refine`. The row SHALL be due on a first run and every `DEFAULT_ROADMAP_ALTERNATIVES_INTERVAL_MINUTES` (1440) after its last success, and SHALL be due by no webhook hint. It SHALL check at most `roadmap.alternatives.limit` items in a round, and SHALL fail the round, once the other checks are written, when the check of any item failed. `devops roadmap run --dry-run` SHALL list the row when it is due.

#### Scenario: A first run
- **WHEN** a round runs on a roadmap whose `schedule.json` holds no success of the row
- **THEN** the row runs once, after `refine`, with the job's plan and apply functions

#### Scenario: Once a day
- **WHEN** the row succeeded 2 hours ago and a round runs
- **THEN** the row does not run, and when the row succeeded 25 hours ago it runs

#### Scenario: A webhook hint
- **WHEN** a round runs with a webhook hint that makes intake due and the row succeeded 2 hours ago
- **THEN** the row does not run

#### Scenario: The limit of a round
- **WHEN** `roadmap.alternatives.limit` is 2 and 4 items have no check
- **THEN** the round checks the 2 lowest numbers

#### Scenario: A failed check
- **WHEN** the model call for one item fails and the call for another succeeds
- **THEN** the check of the second item is written and the row fails, naming the first

#### Scenario: A dry run lists the row
- **WHEN** `devops roadmap run --dry-run` runs on a roadmap whose rows are all due
- **THEN** its `Due:` line ends with `alternatives`, after `refine`

### Requirement: The limit of a round is a setting
`roadmap.alternatives.limit` (default 5, at least 1) SHALL be the number of items that the row and `devops roadmap alternatives` check in one run. `--limit` SHALL replace it for one run of the command.

#### Scenario: The command without --limit
- **WHEN** `roadmap.alternatives.limit` is 2 and `devops roadmap alternatives` runs without `--limit` on 4 unchecked items
- **THEN** the plan checks 2 items

#### Scenario: The command with --limit
- **WHEN** `roadmap.alternatives.limit` is 2 and the command runs with `--limit 3` on 4 unchecked items
- **THEN** the plan checks 3 items

### Requirement: Each written check counts once by its verdict
The job SHALL add 1 to the counter `devops_cli_roadmap_alternatives_total` with the attribute `verdict` for each check it writes, and SHALL count no plan that it does not write, no check it skips and no failed check.

#### Scenario: Two written checks
- **WHEN** a run writes one `covers` check and one `none` check
- **THEN** the counter has one point with `verdict` `covers` and one with `verdict` `none`

#### Scenario: A plan that is not applied
- **WHEN** a run only plans a check and does not apply it
- **THEN** the counter has no point

#### Scenario: A check skipped because the body changed
- **WHEN** a person edits the body between the read and the write of a check
- **THEN** the job writes no check and counts none

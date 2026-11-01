## REMOVED Requirements

### Requirement: The Service runs the check once a day
**Reason**: The interval is a prime number of minutes, 719, and no longer one day (#2965).
**Migration**: The requirement "The Service runs the check twice a day" replaces it.

## ADDED Requirements

### Requirement: The Service runs the check twice a day
The due table of the roadmap SHALL hold the row `alternatives` in `MODEL_LANE_ROWS`, after `refine`. The row SHALL be due on a first run and every `DEFAULT_ROADMAP_ALTERNATIVES_INTERVAL_MINUTES` (719) after its last success, and SHALL be due by no webhook hint. It SHALL check at most `roadmap.alternatives.limit` items in a round, and SHALL fail the round, once the other checks are written, when the check of any item failed. `devops roadmap run --dry-run` SHALL list the row when it is due.

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
- **WHEN** `roadmap.alternatives.limit` is 2 and 4 items have no check
- **THEN** the round checks the 2 lowest numbers

#### Scenario: A failed check
- **WHEN** the model call for one item fails and the call for another succeeds
- **THEN** the check of the second item is written and the row fails, naming the first

#### Scenario: A dry run lists the row
- **WHEN** `devops roadmap run --dry-run` runs on a roadmap whose rows are all due
- **THEN** its `Due:` line ends with `alternatives`, after `refine`

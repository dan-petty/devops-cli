## ADDED Requirements

### Requirement: An intake candidate that another writer changed logs no result line
When the write of an intake candidate raises `RoadmapItemChangedError`, intake SHALL log no `roadmap job result` line for that candidate, and SHALL still add 1 to `devops_cli_roadmap_intake_candidates_total` with `result=skipped`. The other candidates of the round SHALL each log their line.

#### Scenario: Another writer placed one of three candidates
- **WHEN** the write of candidate 2 of 3 raises `RoadmapItemChangedError` and the other two are placed
- **THEN** intake logs two result lines, `placed` for candidates 1 and 3, and no line for candidate 2

### Requirement: The stage line counts the plan calls of the attempt
The `plan_calls` count of a `stage` result line SHALL be the number of plan calls that the attempt made to the model, also when the client keeps no run trace. An attempt that starts from a kept plan SHALL log its line with no `plan_calls` field, and SHALL NOT write 0.

#### Scenario: A client with no trace
- **WHEN** a plain client with no run trace makes one plan call and the item is staged
- **THEN** the line holds `result=staged` and `plan_calls=1`

#### Scenario: A kept plan
- **WHEN** an earlier attempt kept the plan of an item and the next attempt stages that plan with no plan call
- **THEN** the line holds `result=staged` and no `plan_calls` field

#### Scenario: A new plan after a refused kept plan
- **WHEN** the checks refuse the kept plan of an item, and the attempt stages a new plan from one plan call
- **THEN** the counts of the attempt hold no `plan_calls`, so its line holds no `plan_calls` field

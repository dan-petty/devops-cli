## MODIFIED Requirements

### Requirement: A step records each attempt
The step SHALL add one `attempt` event to the trace for the first run and for each repair round. The event SHALL hold the number of the attempt, the tier, the strategy, the outcome `passed` or `failed`, the failure class of a failed attempt, its evidence, and `repair` or `stop` for what follows. The strategy SHALL be `planned` on attempt 1, `repo_map` on attempt 2, and `tier` on attempt 3 and each later attempt. The evidence SHALL pass the masking of every text of an event.

#### Scenario: A failing check that passes on the second attempt
- **WHEN** `ruff check` exits 1 after the first run, and the model fixes the file in the repair round
- **THEN** the trace holds two `attempt` events: attempt 1 failed with class `lint` and the evidence of `ruff`, followed by `repair`, and attempt 2 passed

#### Scenario: A stop
- **WHEN** the repair rounds are used and the check still fails
- **THEN** the last `attempt` event is failed and followed by `stop`

#### Scenario: A fatal class
- **WHEN** the group changes no file
- **THEN** the trace holds one `attempt` event, failed with class `plan_defect` and followed by `stop`

#### Scenario: The strategy of each attempt
- **WHEN** a stub model fails the first attempt with class test and the repair rounds are 1
- **THEN** the trace holds an attempt event for attempt 1 with strategy planned and one for attempt 2 with strategy repo_map

#### Scenario: An attempt after a failure that selects change_tier
- **WHEN** the first attempt ends on a parser failure and the ladder holds two tiers
- **THEN** the attempt event of the next attempt names the second tier and the strategy tier

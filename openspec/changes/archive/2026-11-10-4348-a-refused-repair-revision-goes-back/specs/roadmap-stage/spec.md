## ADDED Requirements

### Requirement: A refused revision of a repair round returns
A revision of a repair round that the checks refuse SHALL go back to the planner with the refused revision as `previous` and the problem as `problem`, `CONST_ROADMAP_STAGE_GATE_RETURNS` times (one) for each repair round, as a refused first reply does. A revision that the checks accept SHALL cause no extra planner call. A revision that is a placeholder in every text SHALL end the item with no return.

#### Scenario: The first revision is refused and the second passes
- **WHEN** the checks refuse the first revision of a repair round and accept the second
- **THEN** the planner gets a third request with `previous` set to the refused revision and `problem` set to the problem of the checks, and the job stages the second revision

#### Scenario: The revision passes
- **WHEN** the checks accept the first revision of a repair round
- **THEN** the planner gets no return for the round

### Requirement: A revision that stays refused ends the item and is kept
When the checks refuse the returned revision of a repair round, the item SHALL fail with a text that names the review and the problem, the planner SHALL make no further request, and `<n>.refused.json` SHALL hold each refused reply of the item with its problem, the refused revisions included.

#### Scenario: Both revisions are refused
- **WHEN** the checks refuse the revision and the returned revision of a repair round
- **THEN** the item fails, the planner has made three requests, and the failure text holds the problem of the second refusal

#### Scenario: The file holds the earlier replies
- **WHEN** the checks refuse the first reply, accept the reply after the return, and refuse both revisions of the repair round
- **THEN** the file `1.refused.json` holds the refused first reply and both refused revisions, each with its problem

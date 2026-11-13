## MODIFIED Requirements

### Requirement: The repair rounds of the review are a setting with a hard ceiling
The setting `roadmap.stage.verify_repair_rounds` SHALL set the repair rounds of the model review, with a default of 2. The setting `roadmap.stage.verify_repair_rounds_ceiling` SHALL set the most repair rounds of an item, with a default of 4. The settings load SHALL refuse a value of `verify_repair_rounds` above `verify_repair_rounds_ceiling` with an error that names both settings, and a value of either setting above 16, 4 times the default of the ceiling.

#### Scenario: The setting sets the rounds
- **WHEN** `roadmap.stage.verify_repair_rounds` is 1 and each review returns the plan
- **THEN** the planner gets 2 requests and the verifier gets 2 requests

#### Scenario: A value over the ceiling
- **WHEN** the settings load reads `roadmap.stage.verify_repair_rounds` of 5 with no ceiling set, or of 17
- **THEN** the load fails with an error that names `verify_repair_rounds`

### Requirement: One more repair round follows while a review fixes more findings than it adds
After the last repair round of the setting, the stage SHALL start one more round only while the last review marked more earlier findings `gone` than it opened new findings, with no model call. No item SHALL get more repair rounds than `roadmap.stage.verify_repair_rounds_ceiling`, and no round SHALL start after the Service stops. Each round past the setting SHALL log `stage review extended:` with the round and the counts of fixed and added findings.

#### Scenario: A review fixes an earlier finding after the last round
- **WHEN** the setting is 2, the first review opens 3 findings, the second review marks each of them `holds`, the third review marks one `gone` and opens no new finding, and the fourth review marks each finding `gone`
- **THEN** the planner gets 4 requests, the staged change holds no open finding, the job logs one `stage review extended:` line with `round=3 fixed=1 added=0`, and the result line counts 4 review runs

#### Scenario: A review fixes as many findings as it adds
- **WHEN** the setting is 2, the first review opens 3 findings, the second review marks one `gone`, and the third review marks one `gone` and opens 1 new finding in the changed text
- **THEN** the planner gets 3 requests, the staged change holds 2 open findings, and the job logs no `stage review extended:` line

#### Scenario: No round past the ceiling
- **WHEN** the setting is 2 and each later review marks one earlier finding `gone` and opens no new finding
- **THEN** the planner gets 1 + `roadmap.stage.verify_repair_rounds_ceiling` requests: 5 at the default ceiling, and 7 when the ceiling is 6

#### Scenario: No round in a drain
- **WHEN** the Service stops during the first review, and the review returns the plan
- **THEN** no repair round starts, the planner gets 1 request, and the item ends with the stop

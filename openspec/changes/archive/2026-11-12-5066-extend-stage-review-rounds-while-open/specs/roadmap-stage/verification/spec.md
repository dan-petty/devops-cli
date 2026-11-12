## RENAMED Requirements

- FROM: `### Requirement: An evidence-backed finding returns the plan at most twice`
- TO: `### Requirement: An evidence-backed finding returns the plan for the set repair rounds`

## MODIFIED Requirements

### Requirement: An evidence-backed finding returns the plan for the set repair rounds
A finding of type `missing_path`, `false_premise`, `ignores_existing_code`, `task_order` or `verify_form` whose quote is in the issue, the plan, a cited file or a tool answer of the run SHALL return the plan to the planner, with each open finding of the round as the problem. The revised plan SHALL pass the gates and the verification again, at most `roadmap.stage.verify_repair_rounds` times, which is two by default, and for each extra round that the rule of the extension allows.

#### Scenario: A false premise with a quote
- **WHEN** the verifier returns a `false_premise` finding whose quote is in the issue
- **THEN** the planner gets a second request with the finding as `problem` and the first plan as `previous`, and the job opens the draft pull request with the revised plan

#### Scenario: A quote that is not in the input
- **WHEN** the verifier returns a `false_premise` finding whose quote is in none of the issue, the plan, the cited files and the tool answers of the run
- **THEN** the planner gets no second request and the finding goes into the comment

#### Scenario: The revised plan has a finding too
- **WHEN** the first revised plan gets a `missing_path` finding with a quote
- **THEN** the planner gets a second repair request with the finding as `problem`

#### Scenario: A task order finding returns the plan
- **WHEN** the verifier returns a `task_order` finding whose quote is in the plan
- **THEN** the planner gets a second request with the finding as `problem`

#### Scenario: A quote from a tool answer
- **WHEN** the verifier reads a line past the cap of a cited file with a tool, and returns an `ignores_existing_code` finding that quotes that line
- **THEN** the planner gets a repair request with the finding as `problem`

## ADDED Requirements

### Requirement: The repair rounds of the review are a setting with a hard ceiling
The setting `roadmap.stage.verify_repair_rounds` SHALL set the repair rounds of the model review, with a default of 2. The settings load SHALL refuse a value above `CONST_ROADMAP_STAGE_VERIFY_REPAIR_ROUNDS_CEILING`, which is 4.

#### Scenario: The setting sets the rounds
- **WHEN** `roadmap.stage.verify_repair_rounds` is 1 and each review returns the plan
- **THEN** the planner gets 2 requests and the verifier gets 2 requests

#### Scenario: A value over the ceiling
- **WHEN** the settings load reads `roadmap.stage.verify_repair_rounds` of 5
- **THEN** the load fails with an error that names `verify_repair_rounds`

### Requirement: One more repair round follows while the open findings drop
After the last repair round of the setting, the stage SHALL start one more round only while the last review has fewer open findings than the review before it. The check SHALL compare counts and make no model call. No item SHALL get more repair rounds than `CONST_ROADMAP_STAGE_VERIFY_REPAIR_ROUNDS_CEILING`. No repair round SHALL start after the Service stops. Each round past the setting SHALL log the line `stage review extended:` with the round and the two counts.

#### Scenario: The open count drops after the last round
- **WHEN** the setting is 2 and the reviews return the plan with 3, 3, 2 and then 0 open findings
- **THEN** the planner gets 4 requests, the staged change holds no open finding, the job logs one `stage review extended:` line with `round=3 before=3 open=2`, and the result line counts 4 review runs

#### Scenario: The open count stays the same
- **WHEN** the setting is 2 and the reviews return the plan with 3, 2 and then 2 open findings
- **THEN** the planner gets 3 requests and the job logs no `stage review extended:` line

#### Scenario: No round past the ceiling
- **WHEN** the setting is 2 and each review returns the plan with one open finding fewer than the review before it
- **THEN** the planner gets 1 + `CONST_ROADMAP_STAGE_VERIFY_REPAIR_ROUNDS_CEILING` requests

#### Scenario: No round in a drain
- **WHEN** the Service stops during the first review, and the review returns the plan
- **THEN** no repair round starts, the planner gets 1 request, and the item ends with the stop

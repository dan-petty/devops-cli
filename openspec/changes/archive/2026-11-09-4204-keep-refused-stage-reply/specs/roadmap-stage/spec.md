## ADDED Requirements

### Requirement: A refused reply is logged
The stage job SHALL log one line `stage reply refused` for each reply of the model that it refuses, with the number of the item, the number of the last request of the plan run, the input of that request in tokens, whether that request offered a function tool, and the result `refused` or `degenerate`.

#### Scenario: A reply that the gates refuse
- **WHEN** the gates refuse the reply of item 1 in the second request of a plan run, and that request offered a tool
- **THEN** the log holds one line with `item=#1`, `request=2`, the input of the request in tokens, `tools_offered=True` and `result=refused`

### Requirement: A failed item keeps its refused replies
When a plan fails, the stage job SHALL write the refused replies and their problems to the file `<n>.refused.json` beside the plan file of item `<n>`, under the key of the plan input. A new failed plan SHALL replace the file, and the staging of the item SHALL delete it. A reply over the byte bound SHALL be dropped with its size kept, and a problem SHALL be masked for secrets and cut to the character bound.

#### Scenario: The gates refuse a plan twice
- **WHEN** the gates refuse the first reply and the reply after the return of item 1
- **THEN** the file `1.refused.json` holds the key and both replies, each with its problem, and no plan file exists

#### Scenario: The item is staged
- **WHEN** a later round stages item 1
- **THEN** the file `1.refused.json` is deleted

### Requirement: A reply of placeholders ends the item
The stage job SHALL end an item at once, with no second request, when a reply is a placeholder in `why`, `existing_tool`, each line of `feasibility` and each task of each group. The item SHALL fail with the error `RoadmapStageDegenerateError`, the job SHALL keep the reply as a refused reply, and `devops_cli_roadmap_stage_total` SHALL count the item under the result `degenerate`. A reply with one text that is no placeholder SHALL go back to the model once.

#### Scenario: The first reply is all placeholders
- **WHEN** the first reply of item 1 holds `x` or `placeholder` in every text of the plan
- **THEN** the model gets one request, the item fails with `RoadmapStageDegenerateError`, and the result of the item is `degenerate`

#### Scenario: A reply with one real text
- **WHEN** the first reply holds `x` in `why` and in `feasibility` and a real text in `existing_tool`
- **THEN** the reply goes back to the model once, as for any refused reply, and the result stays `failed` if the second reply is refused

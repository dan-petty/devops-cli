## MODIFIED Requirements

### Requirement: A refused reply is logged
The stage job SHALL log one line `stage reply refused` for each reply of the model that it refuses, with the number of the item, the number of the last request of the plan run, the input of that request in tokens, whether that request offered a function tool, the number of tool calls of the run, the limit that ended its tools, the stop reason and the model name of the last reply, and the result `refused` or `degenerate`. A fact that the run does not hold SHALL be written as `none`.

#### Scenario: A reply that the gates refuse
- **WHEN** the gates refuse the reply of item 1 in the second request of a plan run, and that request offered a tool
- **THEN** the log holds one line with `item=#1`, `request=2`, the input of the request in tokens, `tools_offered=True` and `result=refused`

#### Scenario: A degenerate reply that a provider stopped at its length
- **WHEN** the reply of item 1 is a placeholder in every text, after one tool call, and its stop reason is `length` and its model name is `fallback-model`
- **THEN** the log holds one line with `tool_calls=1`, `limit=none`, `finish_reason=length`, `answered=fallback-model` and `result=degenerate`

#### Scenario: A plan with no run
- **WHEN** the gates refuse a kept plan that no toolbox run made
- **THEN** the log holds one line with `tool_calls=0`, `limit=none`, `finish_reason=none` and `answered=none`

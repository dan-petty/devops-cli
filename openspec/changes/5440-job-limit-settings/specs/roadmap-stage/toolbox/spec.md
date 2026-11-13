## MODIFIED Requirements

### Requirement: A call to a tool that is gone gets a retry
When a request offers no tool, a call of the model to a function tool SHALL get a retry prompt, and the run SHALL go on. The run SHALL fail the item when the model calls a gone tool a third time, because the tool retry limit is 2. The reason of the failure SHALL name the retry limit, and no budget limit. It holds no tool name, because the name of a tool in an error message is text that the model chose.

#### Scenario: One call after the tools are gone
- **WHEN** the model has made `roadmap.stage.max_tool_calls` minus 3 tool calls, calls `read_file` once in a request that offers no tool, and then gives a valid plan
- **THEN** the item is staged

#### Scenario: Two calls after the tools are gone
- **WHEN** the model calls `read_file` twice in requests that offer no tool, and then gives a valid plan
- **THEN** the item is staged

#### Scenario: Three calls after the tools are gone
- **WHEN** the model calls `read_file` a third time in requests that offer no tool
- **THEN** the item fails, and the reason names the retry limit 2, and no budget limit

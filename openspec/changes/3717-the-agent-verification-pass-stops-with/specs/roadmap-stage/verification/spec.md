## ADDED Requirements

### Requirement: A text reply that holds the findings gives them
The verification pass SHALL accept a plain-text reply that holds the findings in place of a call to the output tool, and SHALL give the findings that the text validates against the schema.

#### Scenario: A text reply holds the findings
- **WHEN** A scripted model replies in text with the findings JSON and calls no output tool.
- **THEN** The run returns those findings and records no stop.

#### Scenario: A text reply holds no findings
- **WHEN** A scripted model replies in text with no findings and calls no output tool.
- **THEN** The run stops with the reason `text_reply` and a message that names the text reply.

### Requirement: A stopped verification run names its cause
The verification pass MUST map a stop of its agent run to a typed reason and a message that a person can act on.

#### Scenario: A tool call that the run does not offer
- **WHEN** A scripted model calls a tool that the run does not offer three times.
- **THEN** The run stops with the reason `refused_tool_call` and the name of the tool.

#### Scenario: The output retries are exhausted
- **WHEN** A scripted model gives an invalid findings call three times and the output retry limit is two.
- **THEN** The run stops with the reason `output_retries_exhausted` and names the retry limit 2.

#### Scenario: The budget is exhausted
- **WHEN** A scripted run reaches the tool-call limit.
- **THEN** The run stops with the reason `budget_exhausted` and the name of the limit.

## ADDED Requirements

### Requirement: A stopped verification run names its cause
The verification pass MUST map a stop of its agent run to a typed reason and a message that names the tool of a refused call, the tool of an offered call whose arguments break its schema, the limit that ended the tools, the output retry limit, or the text reply that pydantic-ai refuses. A call to a tool that the run offers MUST NOT give the reason `refused_tool_call`.

#### Scenario: A text reply that pydantic-ai refuses
- **WHEN** A scripted model replies in text that holds no findings and calls no output tool.
- **THEN** The run stops with the reason `text_reply` and a message that names the text reply.

#### Scenario: A tool call that the run does not offer
- **WHEN** A scripted model calls a tool that the run does not offer until the tools retry limit is spent.
- **THEN** The run stops with the reason `refused_tool_call`, the name of the tool and the retry limit that the run used.

#### Scenario: An offered tool gets arguments that break its schema
- **WHEN** A scripted model calls a tool that the run offers, with arguments that break the schema of the tool, until the tools retry limit is spent.
- **THEN** The run stops with the reason `tool_retries_exhausted`, the name of the tool and the retry limit that the run used, and the message does not say that the run does not offer the tool.

#### Scenario: A tool call holds arguments that are no JSON text
- **WHEN** A scripted model calls a tool that the run offers with arguments that are no JSON text, as when a gateway joins the arguments of two calls.
- **THEN** The run stops with the reason `invalid_arguments` and the name of the tool, and the message names the invalid arguments.

#### Scenario: The output retries are exhausted
- **WHEN** A scripted model gives an invalid findings reply until the output retry limit is spent.
- **THEN** The run stops with the reason `output_retries_exhausted` and a message that names the output retry limit that the run used.

#### Scenario: The budget is exhausted
- **WHEN** A scripted run reaches the tool-call limit.
- **THEN** The run stops with the reason `budget_exhausted` and the name of the limit.

## ADDED Requirements

### Requirement: The refine stop names the tool
When a refine investigation stops after a model response or tool call retry, the stop reason MUST record the tool name that failed or exceeded retries and the sorted list of registered tool names, with no raw reply text.

#### Scenario: A model calls a tool that the investigation did not register
- **WHEN** the investigation runs against a pydantic-ai `FunctionModel` that returns a tool call named `<text>` on every turn
- **THEN** the stop reason holds `tool=<text>` and the registered tool names

### Requirement: The refine stop records the output mode and the parts
When a refine investigation stops after a model response, the stop reason MUST record its structured-output mode and the `part_kind` values of each part in the last model response.

#### Scenario: The model returns text in place of the output call
- **WHEN** the investigation runs with `NativeOutput` against a pydantic-ai `FunctionModel` that returns a text part and no output tool call
- **THEN** the stop reason states `output_mode=NativeOutput` and `parts=[text]`

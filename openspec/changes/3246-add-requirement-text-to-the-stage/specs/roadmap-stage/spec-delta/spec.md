## ADDED Requirements

### Requirement: The stage prompt names modified for a stated behavior
The planner prompt SHALL tell the planner to change a requirement of the requirement text of the context with modified when that requirement states the behavior.

#### Scenario: The rendered planner prompt
- **WHEN** The stage job renders the planner prompt.
- **THEN** The prompt holds the instruction to use modified for a requirement that states the behavior, and the test asserts its text.

## MODIFIED Requirements

### Requirement: The model input holds the purpose and the requirement names of each capability
The stage job SHALL give the model every capability under the specs folder. A plan run that offers the read-spec tool SHALL get the names of the capabilities and the text of the matching base requirements in the first request, and SHALL read the purpose and the requirement names of one capability with that tool. A call with no tool SHALL get the purpose and the requirement names of every capability in the input.

#### Scenario: The input lists a capability
- **WHEN** The stage job builds the model input for a proposal that is planned with one call and no tool.
- **THEN** The input holds the purpose and the requirement names of each capability.

#### Scenario: The input of a run with the read-spec tool
- **WHEN** The stage job builds the first request of a plan run that offers the read-spec tool, for a checkout with many capabilities.
- **THEN** The `capabilities` key holds the name of every capability in order, the context holds the name and the text of each matching requirement, and the run offers the read-spec tool.

#### Scenario: The input of a run with read_spec
- **WHEN** The stage job builds the first request of a plan run that has `read_spec`, for a checkout with many capabilities
- **THEN** the `capabilities` key holds the name of every capability in order, the request holds no purpose and no requirement name, and the run offers `read_spec`

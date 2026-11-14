## ADDED Requirements

### Requirement: The stage prompts name the test module of a changed function
The stage prompt of a run with the toolset `extended` SHALL tell the planner to call `references` for the function whose behavior a behavior group changes and to write the group's `test` in a test module that the answer lists. The stage prompts SHALL tell the planner to write the group's `test` in the test module that `probes` names for that function.

#### Scenario: The extended prompt names the tool
- **WHEN** the system text of a run with the toolset `extended` is built
- **THEN** it holds a sentence that names `references` and the test module that the answer lists

#### Scenario: The base prompt names the probes
- **WHEN** the system text of a run with the toolset `base` is built
- **THEN** it holds a sentence that names `probes` as the source of the test module

## ADDED Requirements

### Requirement: The plan-state comment reads as made at its last edit
The jobs SHALL give their model the plan-state comment of a plan pull request at the place and the time of its last edit, because the jobs edit it in place. Every other comment SHALL keep the place and the time of its creation. The label of a comment in the index SHALL skip each hidden line, such as a marker or a key line, and SHALL show the first line of text.

#### Scenario: An edited state comment comes after an older comment
- **WHEN** a state comment made before a comment of a person was edited after it
- **THEN** the state comment comes after the comment of the person, at the time of its edit

#### Scenario: The label of a comment with a key line
- **WHEN** a comment starts with the marker of the stage job and the key line of a state comment
- **THEN** the label in the index is the first line of text after them

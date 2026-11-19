## MODIFIED Requirements

### Requirement: Only a person's decision waits on a person
A question of kind `person` SHALL be an open question with "(a person decides)", and the item SHALL wait on a person. An open question with no such mark SHALL NOT make an item wait on a person.

#### Scenario: A decision that AGENTS.md reserves for a person
- **WHEN** the proposal asks "Which repository secret holds the key?" as a `person` question and the proposal passes its form check
- **THEN** the item waits on a person, the Open questions of its refine section hold "Which repository secret holds the key? (a person decides)", and the comment names Open questions

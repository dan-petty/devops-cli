## ADDED Requirements

### Requirement: The plan reader keeps the document work of a group
The plan reader SHALL return the document work of a group from a document task that the renderer writes.

#### Scenario: The document mark matches the new template
- **WHEN** The plan reader builds a proposal from a change folder whose group renders a document task
- **THEN** The document work of the group is present in the built proposal.

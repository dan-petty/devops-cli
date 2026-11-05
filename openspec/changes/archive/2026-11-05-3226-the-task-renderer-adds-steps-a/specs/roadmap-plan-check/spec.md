## ADDED Requirements

### Requirement: The plan reader keeps the document work of a group
The plan reader SHALL return the document work of a group from a documentation task that the renderer writes, with the verb that the renderer gives it.

#### Scenario: The document mark matches the new template
- **WHEN** the plan reader builds a proposal from a change folder whose group renders a documentation task that changes only `SECURITY.md`
- **THEN** the document work of the group is present in the built proposal and reads `Edit `SECURITY.md``.

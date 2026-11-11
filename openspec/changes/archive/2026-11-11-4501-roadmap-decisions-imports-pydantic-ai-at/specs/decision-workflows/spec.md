## ADDED Requirements

### Requirement: The settings check the modes without the points
The settings SHALL check the keys and the modes of `roadmap.decisions` against a table of the name and the cuts file of each point, and SHALL NOT import `pydantic_ai` or a point module to do it. The table SHALL hold the same names and cuts files as the registry.

#### Scenario: The table and the registry agree
- **WHEN** a test reads the table and the registry
- **THEN** the names and the cuts files of the two are equal

#### Scenario: On without a cuts file
- **WHEN** a test checks the mode `on` for a point of a table whose cuts file does not exist
- **THEN** the check fails and the error names the point and the file

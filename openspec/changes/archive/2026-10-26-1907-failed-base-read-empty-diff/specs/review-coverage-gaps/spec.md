# Spec Delta

## ADDED Requirements

### Requirement: A base revision file that cannot be read is a coverage gap
A review SHALL record each base revision file that it cannot read as a coverage gap with the reason `Base revision: <error>`. A base revision file that does not exist SHALL NOT be a coverage gap.

#### Scenario: A base revision file read fails from GitHub
- **WHEN** a pull request review reads a base revision file and the GitHub API returns an error
- **THEN** the review records the file as a coverage gap with the reason `Base revision: <error>`
- **AND** the review continues scanning the remaining candidate files

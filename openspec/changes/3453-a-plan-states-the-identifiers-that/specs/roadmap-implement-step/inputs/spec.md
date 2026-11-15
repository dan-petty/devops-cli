## ADDED Requirements

### Requirement: A task group exposes the identifiers that it adds
`TaskGroup.added_names` of `src/devops_cli/roadmap/step_files.py` SHALL give the identifiers of the `Adds:` line of the group, each once, in file order, and SHALL give no name for a group with no such line.

#### Scenario: A task group with two added identifiers
- **WHEN** a group holds `Adds:` with `_delivery_title` and `_publish` in code spans
- **THEN** `TaskGroup.added_names` gives the two names in that order

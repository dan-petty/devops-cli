## ADDED Requirements

### Requirement: The eval compares the tool modes
`devops roadmap eval implement` SHALL accept `--no-tools`, which runs the selected fixtures with the remote MCP tools of the step off, and SHALL record the tool mode in its report beside the model.

#### Scenario: One fixture set in both modes
- **WHEN** A test runs `devops roadmap eval implement --dry-run` on one fixture, then again with the `--no-tools` option.
- **THEN** Both runs name the same fixture and base commit, and each run states its tool mode in the report.

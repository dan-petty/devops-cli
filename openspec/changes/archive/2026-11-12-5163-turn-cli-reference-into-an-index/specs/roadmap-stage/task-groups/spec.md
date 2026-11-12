## MODIFIED Requirements

### Requirement: A documentation task runs the regeneration step for a command change
A documentation task SHALL end with the command `uv run devops docs generate` only when the group changes a path under `src/devops_cli/commands/` or `src/devops_cli/lang/`. A documentation task of any other group SHALL hold the documentation text and no regeneration command.

#### Scenario: A group that changes a document only
- **WHEN** a group has a `documentation` task and changes only `SECURITY.md`
- **THEN** its last task holds the documentation text with no regeneration command, and its `Verification:` line holds `uv run devops ci docs`

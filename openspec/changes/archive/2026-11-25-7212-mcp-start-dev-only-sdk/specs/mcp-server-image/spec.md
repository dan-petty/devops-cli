## ADDED Requirements

### Requirement: The commands import with no dev-only package
Each module of `devops_cli.commands` SHALL import in an install with no `dev` dependency group, such as the `mcp-server` image.

#### Scenario: Dev-only packages are blocked
- **WHEN** a Python process blocks each package of the `deptry` rule `DEP004` and imports each module of `devops_cli.commands`
- **THEN** no import fails

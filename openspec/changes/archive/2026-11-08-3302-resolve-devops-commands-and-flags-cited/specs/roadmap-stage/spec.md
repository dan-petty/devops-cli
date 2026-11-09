## ADDED Requirements

### Requirement: Resolve cited command spans
The plan check SHALL resolve every `devops` command span in the Feasibility text and the task text against the real command tree.

#### Scenario: Unknown subcommand is refused
- **WHEN** A plan cites `uv run devops ai ast-graph --help`.
- **THEN** The check returns a problem that names `ai ast-graph` and refuses the plan.

### Requirement: Accept a resolved command span
The plan check SHALL accept a `devops` command span that resolves to a leaf command with valid options.

#### Scenario: Known subcommand is accepted
- **WHEN** A plan cites `uv run devops ai ast graph --help`.
- **THEN** The check returns no command-resolution problem for that span.

### Requirement: Resolve cited option flags
The plan check SHALL resolve each option flag in a cited `devops` command span against that command.

#### Scenario: Unknown option is refused
- **WHEN** A plan cites `uv run devops gh pages verify --root_dir .`.
- **THEN** The check returns a problem that names `--root_dir` and refuses the plan.

#### Scenario: Known option is accepted
- **WHEN** A plan cites `uv run devops gh pages verify --dir .`.
- **THEN** The check returns no command-resolution problem for that span.

### Requirement: Resolve cited MCP exposure keys
The plan check SHALL resolve each quoted tuple key that a plan cites against `CONST_MCP_EXPOSURE_TABLE`.

#### Scenario: Unknown MCP exposure key is refused
- **WHEN** A plan cites the exposure table key `("ai", "ast-graph")`.
- **THEN** The check returns a problem that names `("ai", "ast-graph")` and refuses the plan.

#### Scenario: Known MCP exposure key is accepted
- **WHEN** A plan cites the exposure table key `("ai", "ast", "graph")`.
- **THEN** The check returns no MCP exposure problem for that key.

# devcontainer-agent-config Specification

## Purpose
The MCP configuration file that each supported coding agent reads in a scaffolded repository, so the `devops-cli` server is available to Kilo Code as it is to the other agents.

## Requirements

### Requirement: The devcontainer scaffold writes a Kilo Code MCP configuration
`devops devcontainer init` SHALL write `kilo.jsonc` at the repository root. The file SHALL declare the server under `mcp` with `type` `local`, the command as one array and the variables as `environment`. The server SHALL start with the same command and variables as the server of `.mcp.json`.

#### Scenario: The scaffold runs in an empty directory
- **WHEN** a test runs `devops devcontainer init` in an empty directory with the name `test-project`
- **THEN** `kilo.jsonc` exists at the root
- **AND** its `mcp` object holds the one key `test-project`

#### Scenario: The Kilo server differs from the Claude server
- **WHEN** a test renders the Kilo and the Claude templates for one project name
- **THEN** the `command` array of the Kilo server is the `command` followed by the `args` of the Claude server
- **AND** its `environment` equals the `env` of the Claude server

### Requirement: The post-start sync writes a missing Kilo Code configuration
`devops devcontainer post-start` SHALL write `kilo.jsonc` in a workspace that has a `pyproject.toml` and no `kilo.jsonc`. It SHALL leave an existing file unchanged.

#### Scenario: A workspace has no Kilo configuration
- **WHEN** a test runs `devops devcontainer post-start` for a workspace with a `pyproject.toml` and no `kilo.jsonc`
- **THEN** `kilo.jsonc` exists in the workspace

### Requirement: The devcontainer scaffold writes Claude Code settings and Antigravity customizations
`devops devcontainer init` SHALL write `.claude/settings.json` with project command allowlists, secret-file read/edit denies, and telemetry opt-out variables (`DO_NOT_TRACK`, `OPENSPEC_TELEMETRY`, `OPENSPEC_NO_UPDATE_CHECK`, `PYDANTIC_AI_NO_BANNER`), and SHALL write `customizations.antigravity` in `.devcontainer/devcontainer.json` matching `customizations.vscode`.

#### Scenario: The scaffold runs in an empty directory
- **WHEN** a test runs `devops devcontainer init` in an empty directory
- **THEN** `.claude/settings.json` exists with `permissions.allow`, `permissions.deny`, and `env`
- **AND** `.devcontainer/devcontainer.json` defines `customizations.antigravity` matching `customizations.vscode`

### Requirement: Project skills stay synchronized across all three agent skill roots
Every skill directory in `.agents/skills/`, `.claude/skills/`, and `.kilocode/skills/` (`devops-openspec-new`, `devops-pr-ci`, `devops-review`, `devops-roadmap`, and `new-scaffold`) SHALL exist in all three roots with identical `SKILL.md` content.

#### Scenario: The skill roots are compared
- **WHEN** the invariant test inspects `.agents/skills`, `.claude/skills`, and `.kilocode/skills`
- **THEN** all three directories contain the same five skill folders and identical `SKILL.md` files

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
Every skill directory in `.agents/skills/`, `.claude/skills/`, and `.kilocode/skills/` (`ask-jev`, `devops-openspec-new`, `devops-pr-ci`, `devops-review`, `devops-roadmap`, and `new-scaffold`) SHALL exist in all three roots with identical `SKILL.md` content.

#### Scenario: The skill roots are compared
- **WHEN** the invariant test inspects `.agents/skills`, `.claude/skills`, and `.kilocode/skills`
- **THEN** all three directories contain the same six skill folders and identical `SKILL.md` files

### Requirement: Claude Code sessions run uv with no environment warning and no bytecode line
The `env` of `.claude/settings.json` and of its template SHALL set `VIRTUAL_ENV` to an empty value and `UV_COMPILE_BYTECODE` to `0`. Then `uv run` in a git worktree uses the `.venv` of the worktree and writes no `VIRTUAL_ENV` warning and no `Bytecode compiled` line.

#### Scenario: The scaffold writes the Claude settings
- **WHEN** `devops devcontainer init` writes `.claude/settings.json`
- **THEN** its `env` holds `VIRTUAL_ENV` with the empty value and `UV_COMPILE_BYTECODE` with the value `0`

#### Scenario: A Claude Code session runs uv in a worktree
- **WHEN** the session starts with `VIRTUAL_ENV` set to the main `.venv` and runs `uv run python` in a git worktree
- **THEN** uv writes no `VIRTUAL_ENV` warning and no `Bytecode compiled` line, and `sys.prefix` names the `.venv` of the worktree

### Requirement: Remote agent sessions install the git hooks
The SessionStart hook of `.claude/settings.json` and its template SHALL run `uv run pre-commit install` in the project directory when `CLAUDE_CODE_REMOTE` is `true` and `uv` and `.pre-commit-config.yaml` exist. Else it SHALL exit 0 and install no hook. The Copilot setup steps SHALL install the hooks.

#### Scenario: The scaffold writes the Claude settings
- **WHEN** `devops devcontainer init` writes `.claude/settings.json`
- **THEN** `hooks.SessionStart` holds one `command` hook with the matcher `startup|resume`

#### Scenario: A cloud session starts
- **WHEN** the hook command runs in a clone with `CLAUDE_CODE_REMOTE` set to `true`
- **THEN** `.git/hooks/pre-commit` and `.git/hooks/pre-push` exist, and the exit code is 0

#### Scenario: A local session starts
- **WHEN** the hook command runs in a clone with no `CLAUDE_CODE_REMOTE`
- **THEN** the clone has no installed hook, and the exit code is 0

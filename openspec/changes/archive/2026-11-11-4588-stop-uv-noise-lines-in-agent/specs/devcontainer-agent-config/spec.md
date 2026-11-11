## ADDED Requirements

### Requirement: Claude Code sessions run uv with no environment warning and no bytecode line
The `env` of `.claude/settings.json` and of its template SHALL set `VIRTUAL_ENV` to an empty value and `UV_COMPILE_BYTECODE` to `0`. Then `uv run` in a git worktree uses the `.venv` of the worktree and writes no `VIRTUAL_ENV` warning and no `Bytecode compiled` line.

#### Scenario: The scaffold writes the Claude settings
- **WHEN** `devops devcontainer init` writes `.claude/settings.json`
- **THEN** its `env` holds `VIRTUAL_ENV` with the empty value and `UV_COMPILE_BYTECODE` with the value `0`

#### Scenario: A Claude Code session runs uv in a worktree
- **WHEN** the session starts with `VIRTUAL_ENV` set to the main `.venv` and runs `uv run python` in a git worktree
- **THEN** uv writes no `VIRTUAL_ENV` warning and no `Bytecode compiled` line, and `sys.prefix` names the `.venv` of the worktree

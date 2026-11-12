## ADDED Requirements

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

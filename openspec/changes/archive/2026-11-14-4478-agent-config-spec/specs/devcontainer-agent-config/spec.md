## MODIFIED Requirements

### Requirement: The devcontainer scaffold writes Claude Code settings and Antigravity customizations
`devops devcontainer init` SHALL write `.claude/settings.json` with the project command allowlist, the deny rules for `--no-verify` on a push or a commit and for a bare `gh` command, and the environment variables `DO_NOT_TRACK`, `OPENSPEC_TELEMETRY`, `OPENSPEC_NO_UPDATE_CHECK` and `UV_MALWARE_CHECK`, and SHALL write `customizations.antigravity` in `.devcontainer/devcontainer.json` matching `customizations.vscode`.

#### Scenario: The scaffold runs in an empty directory
- **WHEN** a test runs `devops devcontainer init` in an empty directory
- **THEN** `.claude/settings.json` exists with `permissions.allow`, `permissions.deny`, and `env`
- **AND** `.devcontainer/devcontainer.json` defines `customizations.antigravity` matching `customizations.vscode`

#### Scenario: The environment matches the template
- **WHEN** the scaffold writes `.claude/settings.json`
- **THEN** its `env` holds `DO_NOT_TRACK`, `OPENSPEC_TELEMETRY`, `OPENSPEC_NO_UPDATE_CHECK` and `UV_MALWARE_CHECK`

#### Scenario: The deny rules match the template
- **WHEN** the scaffold writes `.claude/settings.json`
- **THEN** its `permissions.deny` refuses `--no-verify` on a push or a commit and a bare `gh` command

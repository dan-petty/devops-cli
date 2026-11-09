## ADDED Requirements

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

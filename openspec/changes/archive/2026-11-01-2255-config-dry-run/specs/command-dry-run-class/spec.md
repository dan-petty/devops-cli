# command-dry-run-class Specification

## ADDED Requirements

### Requirement: config-request-plans
The `config init` command SHALL carry the `request-plan` dry-run class. Under dry run, it executes zero subprocesses and renders the planned external requests.

#### Scenario: Dry run on config init
- **WHEN** user executes `devops config init --dry-run`
- **THEN** zero subprocesses execute and the planned `gh auth status` command is printed

#### Scenario: JSON dry run on config init
- **WHEN** user executes `devops config init --dry-run --json`
- **THEN** structured JSON with `dry_run: true` and the list of planned requests is printed

### Requirement: config-no-external-request
The ten commands `config audit-keys`, `config audit-stream`, `config auth-headless`, `config env`, `config env-vars`, `config get`, `config output`, `config set`, `config show`, and `config unset` SHALL carry the `no-external-request` dry-run class. `config set` SHALL provide a local preview under `--dry-run` without modifying settings or OS keyring.

#### Scenario: Dry run on config set
- **WHEN** user executes `devops config set test.key test-value --dry-run`
- **THEN** a preview line is printed and no configuration or keyring writes occur

#### Scenario: Dry run on config show
- **WHEN** user executes `devops --dry-run config show`
- **THEN** the command executes locally and renders settings without external requests

### Requirement: workspace-no-external-request
The five commands `workspace add`, `workspace clean`, `workspace generate`, `workspace open`, and `workspace remove` SHALL carry the `no-external-request` dry-run class. `workspace add`, `workspace generate`, and `workspace remove` SHALL provide local previews under `--dry-run` without modifying workspace files.

#### Scenario: Dry run on workspace add
- **WHEN** user executes `devops workspace add . --dry-run`
- **THEN** a preview line is printed and the workspace file is not modified

### Requirement: openspec-no-external-request
The three commands `openspec archive`, `openspec check`, and `openspec regenerate` SHALL carry the `no-external-request` dry-run class, running locally without external requests.

#### Scenario: Dry run on openspec check
- **WHEN** user executes `devops --dry-run openspec check`
- **THEN** the local OpenSpec gate runs and reports findings

### Requirement: docs-no-external-request
The three commands `docs check`, `docs generate`, and `docs sync-readme` SHALL carry the `no-external-request` dry-run class, running locally without external requests.

#### Scenario: Dry run on docs check
- **WHEN** user executes `devops --dry-run docs check`
- **THEN** documentation checks execute locally without external requests

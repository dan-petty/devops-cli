## ADDED Requirements

### Requirement: A generated AGENTS.md names only the detected toolchain and checks

`devops ai agents` SHALL name a toolchain only for a manifest of the project (`pyproject.toml`, `Cargo.toml`, `package.json` or `go.mod`), and a check to run before a push only for a pre-push hook of the project. It SHALL render the `fail-to-pass` sentence only for a Python project, and the OpenSpec sentence only when `openspec/config.yaml` exists.

#### Scenario: A folder holds only Cargo.toml
- **WHEN** `devops ai agents` writes the `AGENTS.md` of a folder that holds only `Cargo.toml`
- **THEN** the file names Rust
- **AND** it holds no "Python", "uv", "pytest", "ruff" or "mypy"

#### Scenario: A folder has no manifest and no hooks
- **WHEN** `devops ai agents` writes the `AGENTS.md` of a folder with no manifest and no pre-push hook
- **THEN** the file has no toolchain line and no check line

#### Scenario: devops-cli keeps its check line
- **WHEN** `devops ai agents` renders the template for devops-cli
- **THEN** the check line names the two pre-push hooks of `.pre-commit-config.yaml`

#### Scenario: The OpenSpec sentence needs the config file
- **WHEN** a project has no `openspec/config.yaml`
- **THEN** the generated `AGENTS.md` does not name OpenSpec

### Requirement: The model path has its own system prompt

The model path of `devops ai agents` SHALL send the `AGENTS.md` task as its system prompt, with the detected toolchains, pre-push checks and documents. It SHALL NOT send a review persona. The project context SHALL hold each detected manifest.

#### Scenario: The model writes the file of a Rust project
- **WHEN** `devops ai agents` calls the model for a folder with `Cargo.toml` and a pre-push hook
- **THEN** the system prompt names the hook command and holds no review persona
- **AND** the user message holds the `Cargo.toml` text

### Requirement: The template keeps the rule titles of AGENTS.md

A test SHALL compare the rule titles of the template, rendered for devops-cli, with the rule titles of `AGENTS.md`, less a named list of the rules that only devops-cli has. A rule title that only `AGENTS.md` adds SHALL fail the test.

#### Scenario: A rule is added only to AGENTS.md
- **WHEN** `AGENTS.md` gets a rule title that the template and the named list do not hold
- **THEN** the rule-title test reports that title

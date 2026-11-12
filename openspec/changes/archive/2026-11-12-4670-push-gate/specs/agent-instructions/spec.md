## MODIFIED Requirements

### Requirement: A generated AGENTS.md names only the detected toolchain and checks

`devops ai agents` SHALL name a toolchain only for a manifest of the project (`pyproject.toml`, `Cargo.toml`, `package.json` or `go.mod`), and a check to run before a push only for a pre-push hook of the project. It SHALL name a local hook with `args` by its `id`, because its `entry` alone is not its command. It SHALL render the `fail-to-pass` sentence only for a Python project, and the OpenSpec sentence only when `openspec/config.yaml` exists.

#### Scenario: A folder holds only Cargo.toml
- **WHEN** `devops ai agents` writes the `AGENTS.md` of a folder that holds only `Cargo.toml`
- **THEN** the file names Rust
- **AND** it holds no "Python", "uv", "pytest", "ruff" or "mypy"

#### Scenario: A folder has no manifest and no hooks
- **WHEN** `devops ai agents` writes the `AGENTS.md` of a folder with no manifest and no pre-push hook
- **THEN** the file has no toolchain line and no check line

#### Scenario: devops-cli keeps its check line
- **WHEN** `devops ai agents` renders the template for devops-cli
- **THEN** the check line names the three pre-push hooks of `.pre-commit-config.yaml`, `branch-current` by its `id`

#### Scenario: The OpenSpec sentence needs the config file
- **WHEN** a project has no `openspec/config.yaml`
- **THEN** the generated `AGENTS.md` does not name OpenSpec

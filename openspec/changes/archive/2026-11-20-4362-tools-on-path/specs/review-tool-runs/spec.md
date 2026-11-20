## ADDED Requirements

### Requirement: A review finds ruff and semgrep on PATH
The Python block check of the review analysis SHALL run the `ruff` on PATH, and the rule pack test SHALL run the `semgrep` on PATH. Each SHALL find its tool through `require_binary` and MUST NOT look in `~/.local/bin` or in another folder of `devops install-tools`. With no tool on PATH, each SHALL raise `DependencyError` with an install hint that names the upstream install page of the tool.

#### Scenario: Semgrep on PATH
- **WHEN** a stand-in `semgrep` is on PATH and `devops review rules test` runs
- **THEN** `semgrep --version` and `semgrep --test` start from the path of the stand-in

#### Scenario: Semgrep only in the installer folder
- **WHEN** a stand-in `semgrep` is in `~/.local/bin` and no `semgrep` is on PATH
- **THEN** the rule pack test raises `DependencyError` with a hint that names `semgrep.dev`, and no process starts

#### Scenario: No ruff on PATH
- **WHEN** no `ruff` is on PATH and the analysis checks a Python block with no checker given
- **THEN** the check raises `DependencyError` with a hint that names the Ruff install page

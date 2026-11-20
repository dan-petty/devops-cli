## MODIFIED Requirements

### Requirement: The record of a program run names the distribution of the tool beside the program
The `version` and the `binary_sha256` of a run that starts from a `program` SHALL name the distribution of the tool in the environment whose scripts directory holds the program. With no such distribution, the `binary_sha256` SHALL be the SHA-256 of the program file, and the `version` SHALL be `unknown`; no pin gives it.

#### Scenario: The interpreter of an environment that holds the tool
- **WHEN** the program is the `python` of a `.venv` that holds mypy 2.3.1, and that `python` is a link to an interpreter outside the `.venv`
- **THEN** the `version` is 2.3.1, and the `binary_sha256` is the one that the mypy launcher of that `.venv` gives
- **AND** it is not the SHA-256 of the interpreter file

#### Scenario: The interpreter of an environment without the tool
- **WHEN** the program is the `python` of a `.venv` that holds no mypy
- **THEN** the `binary_sha256` is the SHA-256 of the interpreter file, and the `version` is `unknown`

### Requirement: The binary digest of a native review tool is the digest of its file
When no distribution in those directories has a console script that wrote the program of a review tool, the `binary_sha256` of a run SHALL be the SHA-256 of the program file. Its `version` SHALL be the version of the installed distribution of that name, else `unknown`. No pin SHALL give the version.

#### Scenario: A native binary
- **WHEN** the kube-linter on PATH is one binary file, and the Ruff on PATH is the binary that the Ruff distribution ships as a file and not as a console script
- **THEN** the `binary_sha256` of each is the SHA-256 of its file
- **AND** the `version` of kube-linter is `unknown`

## ADDED Requirements

### Requirement: A review finds ruff and semgrep on PATH
The Python block check of the review analysis SHALL run the `ruff` on PATH, and the rule pack test SHALL run the `semgrep` on PATH. Each SHALL find its tool through `require_binary` and SHALL look in no other folder. With no tool on PATH, each SHALL raise `DependencyError` with an install hint that names the upstream install page of the tool.

#### Scenario: Semgrep on PATH
- **WHEN** a stand-in `semgrep` is on PATH and `devops review rules test` runs
- **THEN** `semgrep --version` and `semgrep --test` start from the path of the stand-in

#### Scenario: Semgrep only in a folder off PATH
- **WHEN** a stand-in `semgrep` is in `~/.local/bin` and no `semgrep` is on PATH
- **THEN** the rule pack test raises `DependencyError` with a hint that names `semgrep.dev`, and no process starts

### Requirement: A missing ruff reaches the caller of the analysis
The group analysis SHALL look up `ruff` at the first Python block of a reply that parses. A missing `ruff` SHALL reach the caller as `DependencyError`, and no job SHALL record it as a failed model call. A review whose replies hold no such block SHALL need no `ruff`.

#### Scenario: No ruff on PATH and a Python block in a reply
- **WHEN** no `ruff` is on PATH, and the group analysis runs with no checker and a model whose reply holds a Python block
- **THEN** it raises `DependencyError` with the Ruff install hint, and no job records `model-call-error`

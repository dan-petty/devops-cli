## MODIFIED Requirements

### Requirement: The binary digest of a native review tool is the digest of its file
When no distribution in those directories has a console script that wrote the program of a review tool, the `binary_sha256` of a run SHALL be the SHA-256 of the program file. Its `version` SHALL be the version of the installed distribution of that name, else `unknown`. No pin SHALL give the version.

#### Scenario: A native binary
- **WHEN** the kube-linter on PATH is one binary file, and the Ruff on PATH is the binary that the Ruff distribution ships as a file and not as a console script
- **THEN** the `binary_sha256` of each is the SHA-256 of its file
- **AND** the `version` of kube-linter is `unknown`

## ADDED Requirements

### Requirement: A review finds ruff and semgrep on PATH
The Python block check of the review analysis SHALL run the `ruff` on PATH, and the rule pack test SHALL run the `semgrep` on PATH. Each SHALL find its tool through `require_binary` and SHALL look in no other folder. With no tool on PATH, each SHALL raise `DependencyError` with an install hint that names the upstream install page of the tool. The analysis SHALL look up `ruff` before it starts a model job, so a missing `ruff` reaches the caller and no job records it as a failed model call.

#### Scenario: Semgrep on PATH
- **WHEN** a stand-in `semgrep` is on PATH and `devops review rules test` runs
- **THEN** `semgrep --version` and `semgrep --test` start from the path of the stand-in

#### Scenario: Semgrep only in a folder off PATH
- **WHEN** a stand-in `semgrep` is in `~/.local/bin` and no `semgrep` is on PATH
- **THEN** the rule pack test raises `DependencyError` with a hint that names `semgrep.dev`, and no process starts

#### Scenario: No ruff on PATH before a model job
- **WHEN** no `ruff` is on PATH and the group analysis runs with a model client and no checker
- **THEN** it raises `DependencyError` with the Ruff install hint, and the model gets no call

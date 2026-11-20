## MODIFIED Requirements

### Requirement: The binary digest of a native review tool is the digest of its file
When no distribution in those directories has a console script that wrote the program of a review tool, the `binary_sha256` of a run SHALL be the SHA-256 of the program file. Its `version` SHALL be the version of the installed distribution of that name, else `unknown`. No pin SHALL give the version.

#### Scenario: A native binary
- **WHEN** the kube-linter on PATH is one binary file, and the Ruff on PATH is the binary that the Ruff distribution ships as a file and not as a console script
- **THEN** the `binary_sha256` of each is the SHA-256 of its file
- **AND** the `version` of kube-linter is `unknown`

## ADDED Requirements

### Requirement: The rules lock holds no Semgrep version
An entry of `rules.lock` SHALL hold the file names and the SHA-256 digests of a rule and its test, and no Semgrep version. The model of an entry SHALL refuse a `semgrep_version` field. `devops review rules test` SHALL print the version that the installed `semgrep --version` states.

#### Scenario: A lock entry with a Semgrep version
- **WHEN** a test loads a rule-pack lock entry that holds `semgrep_version`
- **THEN** the load raises a validation error that names the field

#### Scenario: The detected version
- **WHEN** a fake `semgrep` prints `1.99.0` and `devops review rules test --check` runs
- **THEN** the command exits 0 and prints `with Semgrep 1.99.0`

#### Scenario: A Semgrep bump runs the rule tests
- **WHEN** `uv run devops ci --check --only actionlint,zizmor` runs on `.github/workflows/rule-pack.yml`, whose paths name `tools.lock` and `semgrep.txt`
- **THEN** actionlint and zizmor report no error

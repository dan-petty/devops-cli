## ADDED Requirements

### Requirement: The rules lock holds no Semgrep version
An entry of `rules.lock` SHALL hold the file names and the SHA-256 digests of a rule and its test, and no Semgrep version. The model of an entry SHALL refuse a `semgrep_version` field. `devops review rules test` SHALL print the version that the installed `semgrep --version` states, and `--check` SHALL compare no Semgrep version.

#### Scenario: A lock entry with a Semgrep version
- **WHEN** a test loads a rule-pack lock entry that holds `semgrep_version`
- **THEN** the load raises a validation error that names the field

#### Scenario: The detected version
- **WHEN** a fake `semgrep` prints `1.99.0` and `devops review rules test --check` runs
- **THEN** the command exits 0 and prints `with Semgrep 1.99.0`

#### Scenario: The Semgrep of the devtools image
- **WHEN** the live check reads the log of the `Rule Pack Tests` job of a pull request, which runs in the devtools image
- **THEN** `devops review rules test --check` exits 0 and names the Semgrep version of the image

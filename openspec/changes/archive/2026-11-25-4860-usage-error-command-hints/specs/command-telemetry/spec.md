## ADDED Requirements

### Requirement: Usage errors print one hint line for known wrong commands and flags
When a CLI command fails with a Click usage error that matches an entry in `usage_hints.yaml`, asks to list CI rows (`devops ci list` or `devops ci --list`), or matches another command path by exact word or hyphen/underscore split across the command tree, the CLI SHALL print one hint line after Click's error box, run no command, and still exit with code 2.

#### Scenario: By-design command removal shows policy hint
- **WHEN** a user runs `devops pr merge 1` or `devops gh pr merge 1`
- **THEN** the CLI exits with code 2, prints Click's error box, and prints one hint line stating that only a person merges a pull request

#### Scenario: Known command synonyms suggest the real command
- **WHEN** a user runs `devops roadmap show 1` or `devops pr show 1`
- **THEN** the CLI exits with code 2 and prints a hint naming `devops roadmap explain <n>` or `devops pr view <n>` respectively

#### Scenario: External tool commands point to both tools
- **WHEN** a user runs `devops openspec validate` or `devops openspec list`
- **THEN** the CLI exits with code 2 and prints a hint naming both the OpenSpec CLI command and `devops openspec check`

#### Scenario: Listing CI gate rows prints CHECK_ROW_NAMES
- **WHEN** a user runs `devops ci list` or `devops ci --list`
- **THEN** the CLI exits with code 2 and prints every row name from `CHECK_ROW_NAMES` on one line

#### Scenario: Interim gh flags point to devops gh api endpoints
- **WHEN** a user runs `devops gh issue view 1 --json number` or `devops pr comment 1`
- **THEN** the CLI exits with code 2 and prints the corresponding `devops gh api` command hint

#### Scenario: Cross-group lookup resolves split words without prefix matching
- **WHEN** a user runs `devops ai cost-report`
- **THEN** the CLI prints `Did you mean: devops ai cost report` and exits with code 2
- **AND** a partial prefix such as `devops ai repo` does not emit a cross-group hint

### Requirement: Option errors omit help options, list small option sets, and show missing-option help
An unknown-option error SHALL exclude `--help` and `-h` from `Possible options`. When no close match remains after exclusion and the command defines at most 6 non-help options, Click's error line SHALL list every non-help option of that command. A `Missing option` error SHALL include the option's help string on the error line.

#### Scenario: Unknown option omits --help and lists small command option sets
- **WHEN** a user runs `devops gh issue view 1 --hel` or `devops gh issue view 1 --bogus`
- **THEN** `--help` and `-h` are absent from `Possible options`
- **AND** `--repo` appears in `Possible options` because `gh issue view` defines at most 6 options

#### Scenario: Missing option includes its help text
- **WHEN** a user runs `devops pr describe 1` without `--summary`
- **THEN** Click's `Missing option` error line includes the help string of `--summary`

### Requirement: Usage error telemetry records whether a hint was shown
`UsageErrorRecord`, the usage ledger JSONL entry, and the `cli_usage_error` log record (`usage.hinted`) SHALL include a boolean `hinted` field that is `true` when an extra hint line matched and `false` otherwise.

#### Scenario: Telemetry records hinted status accurately
- **WHEN** `devops pr merge 1` fails with a hint and `devops gh prr list` fails without an extra hint
- **THEN** the ledger record and `usage.hinted` log attribute are `true` for `pr merge` and `false` for `gh prr`

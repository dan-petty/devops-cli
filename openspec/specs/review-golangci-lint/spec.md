# review-golangci-lint Specification

## Purpose

Configure and run `golangci-lint` v2 flags and YAML configuration for Go static analysis in reviews.

## Requirements

### Requirement: Scan command uses v2 flags
`GolangciLintScanner.build_command` SHALL pass `--output.sarif.path=stdout` for every scan and `--default=none` before the `--enable` of each named linter, and MUST NOT pass `--out-format` or `--disable-all`.

#### Scenario: Default scan command
- **WHEN** `test_golangci_lint_build_command` calls `GolangciLintScanner().build_command(Path("."))`
- **THEN** the command holds `run`, `--output.sarif.path=stdout`, `--default=none`, and one `--enable` for each of `errcheck`, `govet`, and `staticcheck`, with neither `--out-format` nor `--disable-all`

### Requirement: Review config is v2 and accepted by golangci-lint
`CONST_REVIEW_SCAN_GOLANGCI_LINT_CONFIG` SHALL set `version: "2"`, `linters.default: none`, and `linters.settings.govet.enable: [lostcancel]`, with no `linters-settings`, `disable-all`, or `linters.enable` keys, and SHALL pass `golangci-lint config verify`.

#### Scenario: Review config passes schema and live verification
- **WHEN** `CONST_REVIEW_SCAN_GOLANGCI_LINT_CONFIG` is parsed as YAML and passed to `golangci-lint config verify -c`
- **THEN** YAML checks confirm v2 keys without v1 keys, `golangci-lint config verify` exits 0 with no output, and v2.15.0 SARIF parsing returns `Finding` objects

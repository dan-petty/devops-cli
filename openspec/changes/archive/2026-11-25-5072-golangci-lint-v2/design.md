# Design

## Decisions
- Pass `--output.sarif.path=stdout` as a single token and `--default=none` before `--enable <linter>` args in `GolangciLintScanner.build_command`.
- Represent `CONST_REVIEW_SCAN_GOLANGCI_LINT_CONFIG` in v2 YAML (`version: "2"`, `linters.default: none`, `linters.settings.govet.enable: [lostcancel]`) without `linters.enable`, matching `build_command`'s explicit CLI linter selection and verified via `golangci-lint config verify`.
- Strip `REFUSED_STAND_IN_DIRNAME` from `PATH` when invoking the `@pytest.mark.live("golangci-lint")` `config verify` test inside pytest so `refused_program_stand_ins` (`tests/conftest.py`) does not shadow `/usr/local/bin/golangci-lint` with the `exit 127` stand-in, while preserving `_missing_live_binary` skipping on hosts without `golangci-lint`.

## Rejected alternatives
- Keep `linters.enable` in `CONST_REVIEW_SCAN_GOLANGCI_LINT_CONFIG`: mixes CLI and config linter selection when `build_command` dynamically passes `--enable`.
- Add `go` to `RUNNER_TOOLS` or run a live Go scan here: the `devtools:1.1.12` runner image lacks a `go` toolchain; deferred to `#7091`.

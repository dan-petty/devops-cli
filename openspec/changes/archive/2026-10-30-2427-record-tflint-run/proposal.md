# Proposal

## Why

Issue #2427, acceptance criterion 3: each pinned tool has a run with findings, recorded at the pinned version, in `tests/fixtures/scanner_runs/runs_with_findings.json`.
The change that pinned tflint 0.65.0 (`2026-10-29-2427-pin-tflint-dive`) could not record the run, because nobody had approved a run of the downloaded program.
The parser read the report from the tflint source only.
The owner has now approved the run. This change records it.

## What Changes

- `runs_with_findings.json` gets the key `tflint`: version `0.65.0`, the command of the adapter (`tflint --format json --recursive`), `{tree}` as the working directory, exit code 2, the exact stdout of the run, and an empty stderr.
- A test in `tests/security/test_tflint.py` starts the adapter over the fake with `script_run_with_findings("tflint", ...)`. It asserts the command, the status `ran`, and all six findings with their rule, message, severity and relative file name, including the three in `modules/network/main.tf`.
- `test_each_run_with_findings_is_of_the_version_the_tools_lock_pins` now holds the recording to the locked version, with no change to the test.
- The docstring of `tests/support/fakes/scanners.py` names the new recording.
- The parser is correct against the recorded run, so no product code changes (Feasibility).
- The change alters tests only. It has no spec delta and sets `skip_specs: true` in `.openspec.yaml`, as other test-only changes do.
- The change fits in one pull request.

## Impact

- `tests/fixtures/scanner_runs/runs_with_findings.json`
- `tests/security/test_tflint.py`
- `tests/support/fakes/scanners.py`

## Feasibility

The run was made twice with the pinned binary, tflint 0.65.0 with the bundled `terraform` ruleset 0.15.0: once by the owner, and once by the main session on a scratch tree. The change reads the saved output of those runs and starts no downloaded program.

- **Command and exit code.** `tflint --format json --recursive`, started in the directory of the tree. The exit code is 2 (issues found). The stderr is empty.
- **JSON shape.** One object, `{"issues": [...], "errors": []}`. Each issue has `rule` (`name`, `severity`, `link`), `message`, `range` (`filename`, `start` and `end`, each with `line` and `column`), `callers`, `fixable` and `fixed`. This is the shape that the tflint source gave, so the source reading of the earlier change was right.
- **Issues.** The tree has `main.tf` and `modules/network/main.tf`. Each file declares one unused variable with no type. The report has six issues, three for each file: `terraform_typed_variables`, `terraform_unused_declarations` and `terraform_required_version`. All six have the severity `warning`, in lower case.
- **File names.** `range.filename` is relative to the directory that tflint started in: `main.tf` and `modules/network/main.tf`. With `--recursive`, the file of the module reads `<directory>/<file>`. This confirms the inference that the earlier change made from `cmd/inspect.go`. The paths in the recording hold no absolute path, so the recording needs no `{tree}` in stdout.
- **Parser.** `_parse_tflint_issue` gives MEDIUM for `warning`, takes the rule name, the message, the file name and `range.start.line`, and builds `<file>:<line>`. All six findings are right, so the parser does not change. The mapping of `error` and `info` stays from the tflint source and from the earlier tests, because the run has no issue of those severities.
- **Fields that the parser ignores on purpose.** `fixable`, `fixed` and `callers` are not read. `devops` never runs `tflint --fix`, so `fixed` is always false and `fixable` has no use. `callers` is empty unless a rule reads a module call, and the finding already names the file and the line. `rule.link` and `range.end` and the column are not in a `Finding`. The `errors` array is not read: the scanner base reads exit 1 with no issue as a failed scan, and the run has an empty `errors`.
- **Offline.** The test uses the fake and reads the recording. It makes no request and starts no program.

## Existing Tool Considered

tflint (https://github.com/terraform-linters/tflint), pinned in `tools.lock`. The change builds no tool or check. It records the output of the tool, as the recordings of the other pinned scanners do. The change deletes no code.

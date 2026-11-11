# Proposal: #4321

## Why

Issue #4321, and its duplicate #4288: two tests of `tests/commands/test_scan.py` run `devops scan trivy`, `devops scan secrets` and `devops scan sast` with no fake for the scanners. These tests are `test_scan_individual_tools` and the three cases of `test_scan_serialized_output_holds_status_reason_and_findings`. The result of each test depends on the host:

- In the devcontainer, `trivy`, `gitleaks` and `semgrep` are on PATH. The scan starts the real tool, and the floor of the test suite refuses it. The file gives 4 failures and 4 errors, so every full local run of `devops ci` fails.
- On the GitHub runner, no scanner is on PATH. Each scan reports `unavailable`, and the tests pass. They check only that the output holds the keys `status`, `reason` and `findings`, so they do not test a scan that ran.

docs/TESTING.md says that a test whose code starts a scanner asks for `scanner_fake`.

## What Changes

- The two tests ask for `scanner_fake`. The fake puts a stand-in for each scanner first on PATH and answers the request of each scanner to the tool executor. It has recorded runs of Gitleaks and Semgrep. It has no recorded run of Trivy, so the tests script a Trivy run that finds nothing, as other tests of the scan commands do.
- `test_scan_individual_tools` also checks that each command started its own scanner, and that the dry run of `scan secrets` started no scanner.
- `test_scan_serialized_output_holds_status_reason_and_findings` checks the full JSON and YAML output of a scan that ran and found nothing: status `ran`, an empty reason and no findings.

The change alters no behavior that a consumer observes. It changes only one test file and no file under `src/`. So it has no spec delta, and `.openspec.yaml` sets `skip_specs: true`.

The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `tests/commands/test_scan.py`: the two tests use `scanner_fake`.
- No document changes. docs/TESTING.md already describes `scanner_fake` and the rule that this change applies.

## Feasibility

I confirmed the premise in the devcontainer at `origin/main` 1ca0133a:

- `uv run pytest tests/commands/test_scan.py -n 0` gives `4 failed, 21 passed, 4 errors`. The floor reports "host path reached without a fake" for `~/.local/share/devops-cli/tools/trivy/0.75.0/trivy` and for the Gitleaks binary in the same tree, and "process edge reached without a fake" for `semgrep scan`.
- The scanners are on PATH through links in `~/.local/bin` (`which trivy gitleaks semgrep`). With a PATH that holds none of them, the same base file gives `25 passed`, and `devops scan trivy <dir> --json` reports `{"status": "unavailable", "reason": "Binary 'trivy' not found on PATH", "findings": []}`. So on a host without the tools, the base tests pass and test no scan.
- With the change, the file gives `25 passed` with the scanners on PATH and `25 passed` with a PATH that holds none of them. The fixture sets PATH to its own stand-ins and the interpreter, so the host install has no effect.
- `uv run devops ci fail-to-pass --base origin/main` reports `0 failed on base`. The replay runs the changed tests on the `src/` tree of the base, and this change edits no file under `src/`, so the changed tests also pass there. CONTRIBUTING.md gives no fail-to-pass check to a change of tests only. The defect is in the old tests, and the first item above shows it.

## Existing Tool Considered

The project fake `ScannerFake`, behind the `scanner_fake` fixture in `tests/support/fakes/scanners.py`, covers the need. `test_scan_serialized_output_with_findings` in the same file already uses it. No new tool or helper is built.

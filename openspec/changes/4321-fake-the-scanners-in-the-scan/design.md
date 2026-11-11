# Design

## Decisions

- **Fake each scanner at the tool executor seam.** The tests ask for `scanner_fake`. The fixture makes every `DirectToolExecutor` answer through `ScannerFake` and puts the stand-ins of the scanners first on PATH. So `shutil.which` finds a scanner on every host, and no real scanner starts.
- **Script a clean Trivy run.** `tests/fixtures/scanner_runs/recorded_runs.json` has no recorded run of Trivy. The tests script `ToolAnswer(stdout='{"Results": []}')`, a run that exits 0 and finds nothing. `test_scan_serialized_output_with_findings` and `tests/security/test_builtin_tools.py` script Trivy in the same form. Gitleaks and Semgrep answer with their recorded runs, which find nothing.
- **Assert the full result.** With a fake, each scan runs on every host, so the tests can assert the exact output (`status` `ran`, empty `reason`, no findings) and the scanners that each command started, in place of the presence of three keys.

## Rejected alternatives

- **Mark the tests `@pytest.mark.live`.** These are tests of the command output, not integration tests of the tools. A live mark would remove them from CI, and the GitHub runner has no scanners to run them.
- **Skip the tests when a scanner is installed.** The tests would not run in the devcontainer, and the acceptance criteria need a pass on both hosts.
- **Remove the scanners from PATH in the tests.** Each scan would report `unavailable`, so the tests would still test no scan that ran.
- **Record a run of Trivy for `scanner_fake`.** The contract suite would then hold Trivy to its adapter and to the version of `tools.lock`. That is a change to the shared fake and its contract suite, outside this fix. No test of this file needs more than a clean run.

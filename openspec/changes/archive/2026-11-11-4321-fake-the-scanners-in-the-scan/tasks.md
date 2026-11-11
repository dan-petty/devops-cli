# Tasks

## 1. The scan command tests use scanner_fake
kind: other

- [x] 1.1 Give `test_scan_individual_tools` the `scanner_fake` fixture and a scripted clean Trivy run. Assert the exit codes and the scanners that each command started.
  - Verification: `$ uv run devops ci test tests/commands/test_scan.py`
- [x] 1.2 Give `test_scan_serialized_output_holds_status_reason_and_findings` the `scanner_fake` fixture and a scripted clean Trivy run. Assert the full JSON and YAML output.
  - Verification: `$ uv run devops ci test tests/commands/test_scan.py`
- [x] 1.3 Run the file with no scanner on PATH.
  - Verification: `$ env PATH=/usr/local/bin:/usr/bin:/bin uv run pytest tests/commands/test_scan.py -n 0`
- [x] 1.4 Show that the tests of the base fail in the devcontainer, where the scanners are on PATH.
  - Verification: in a checkout of `origin/main` in the devcontainer, run `uv run pytest tests/commands/test_scan.py -n 0`. It gives 4 failures and 4 errors.

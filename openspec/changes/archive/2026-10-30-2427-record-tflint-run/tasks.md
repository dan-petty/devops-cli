# Tasks

## 1. Record the tflint run

- [x] 1.1 Write the failing test: the recorded tflint run gives six findings with their relative file names (`tests/security/test_tflint.py`). Verify with `uv run devops ci fail-to-pass --base origin/main`
- [x] 1.2 Add the key `tflint` to `tests/fixtures/scanner_runs/runs_with_findings.json`, and name the run in the docstring of `tests/support/fakes/scanners.py`. Verify with `uv run devops ci test tests/security/test_tflint.py tests/test_scanner_contract.py`

## 2. Archive

- [x] 2.1 Archive the change. Verify with `uv run devops openspec archive 2427-record-tflint-run`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

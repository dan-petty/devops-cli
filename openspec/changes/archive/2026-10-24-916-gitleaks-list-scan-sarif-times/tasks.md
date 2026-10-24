# Tasks

## 1. Tests for merge_outcomes and Gitleaks SARIF times

- [x] 1.1 Add unit test in `tests/test_scan_outcomes_and_gating.py` verifying `merge_outcomes` preserves the earliest start time and the latest end time (`uv run devops ci test tests/test_scan_outcomes_and_gating.py`)
- [x] 1.2 Add integration test in `tests/test_security_gitleaks.py` verifying a two-file list scan keeps start and end times in the SARIF invocation (`uv run devops ci test tests/test_security_gitleaks.py`)
- [x] 1.3 Run full test and documentation checks (`uv run devops ci test tests/test_security_gitleaks.py tests/test_scan_outcomes_and_gating.py && uv run devops docs generate --sync-readme`)

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

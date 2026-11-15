# Tasks

## 1. Behavior

- [x] 1.1 Write failing tests for connect failure retries and write non-retry
  - Verification: `$ uv run devops ci test tests/github/test_github_session.py`
- [x] 1.2 Extend `_LOST_CONNECTION` in `src/devops_cli/github/session_transport.py` to include `httpx2.ConnectError` and `httpx2.ConnectTimeout`
  - Verification: `$ uv run devops ci test tests/github/test_github_session.py`
- [x] 1.3 Update affected tests in `tests/github/`
  - Verification: `$ uv run devops ci test tests/github/`

## 2. Documents

- [x] 2.1 Add Status History entry to ADR 0006 and verify ADR invariant tests
  - Verification: `$ uv run pytest tests/invariants/test_adr_records.py`
- [x] 2.2 Add spec deltas for `github-session-retry` and `github-session-timeouts`
  - Verification: `$ uv run devops openspec check`

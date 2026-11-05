# Tasks

## 1. Retry a read whose connection is lost

- [ ] 1.1 Write failing tests in `tests/github/test_github_session.py` for a GET that loses its connection once and then answers, for a GET that loses its connection on every attempt, for a POST that loses its connection, for a listing that loses page 3, and for a lost GET that waits through the identity ledger.
  Verification: `uv run devops ci test tests/github/test_github_session.py`
- [ ] 1.2 Retry a lost GET in `SessionGitHubAPI._request` in `src/devops_cli/github/session_transport.py`, with `lost_connection_wait`, and let `refused_retry` in `src/devops_cli/github/error_classifier.py` accept a transport error with no status.
  Verification: `uv run devops ci test tests/github/test_github_session.py tests/github/test_github_errors.py`
- [ ] 1.3 Update the module docstring of `src/devops_cli/github/session_transport.py` to state the lost-connection rule and its budget.
  Verification: `uv run devops ci test tests/github/test_github_session.py`

## 2. Document the retry rule

- [ ] 2.1 Update the Retries paragraph of `docs/adr/0006-github-session-requests-go-through-gidgethub.md` to state that a GET that loses its connection is sent again and a write is not.
  Verification: `uv run devops ci docs`
- [ ] 2.2 Regenerate the documentation with `uv run devops docs generate --sync-readme`.
  Verification: `uv run devops docs check`

## 3. Prove the fix and pass the gate

- [ ] 3.1 Run the fail-to-pass check and confirm that the new tests fail on `origin/main`.
  Verification: `uv run devops ci fail-to-pass --base origin/main`
- [ ] 3.2 Run the full gate with no failure.
  Verification: `uv run devops ci`

## Workflow follow-up

- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
- Pending a person: confirm which image printed the `StreamReset` and `ConnectionTerminated` names in the Service rounds of issue 3506.

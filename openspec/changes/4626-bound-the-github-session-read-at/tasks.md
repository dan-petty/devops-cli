# Tasks

## 1. Behavior: the session read bound and the chain

- [x] 1.1 Add the failing tests: the session's client reads within 60 s, a silent loopback host fails the read at a short bound with `ReadTimeout` and no resend, a release download keeps `DEFAULT_HTTP_TIMEOUT_SECONDS`, and each bound of the chain is shorter than the bound after it
  - Verification: `$ uv run devops ci test tests/github/test_github_session_timeouts.py tests/github/test_github_session.py tests/commands/test_install_tools.py`
- [x] 1.2 Add `DEFAULT_GH_SESSION_READ_TIMEOUT_SECONDS` (60 s) to `config/defaults.py` and pass it as the read bound in `session_client`
  - Verification: `$ uv run devops ci test tests/github/test_github_session_timeouts.py tests/github/test_github_session.py tests/commands/test_install_tools.py tests/github/test_github_contract.py`

## 2. Documents

- [x] 2.1 State the read bound in ADR 0006 (Client)
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- #4573 adds the deadline of the alternatives unit to the chain in `tests/github/test_github_session_timeouts.py` when it adds that deadline.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

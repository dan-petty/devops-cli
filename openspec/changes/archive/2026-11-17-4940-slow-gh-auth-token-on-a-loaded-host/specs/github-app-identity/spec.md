## ADDED Requirements

### Requirement: A timed-out gh auth token lookup is tried again

The process SHALL run `gh auth token` up to `DEFAULT_GH_AUTH_TOKEN_ATTEMPTS` times when an attempt
times out, with the same `DEFAULT_GH_AUTH_TOKEN_TIMEOUT_SECONDS` limit for each attempt. It SHALL
NOT retry an `OSError` or an exit status other than zero. It SHALL keep a token that a retry finds
for the session.

#### Scenario: The first attempt times out and the second answers

- **WHEN** the first `gh auth token` call raises `subprocess.TimeoutExpired` and the second returns
  a token
- **THEN** the lookup returns that token and `run_subprocess` is called exactly twice

#### Scenario: Every attempt times out

- **WHEN** each attempt of `gh auth token` raises `subprocess.TimeoutExpired`
- **THEN** the lookup returns the unauthenticated message, `run_subprocess` is called
  `DEFAULT_GH_AUTH_TOKEN_ATTEMPTS` times, and the message names the time limit

#### Scenario: gh is not on PATH

- **WHEN** the first `gh auth token` call raises `OSError`
- **THEN** the lookup returns the not-found message and `run_subprocess` is called exactly once

#### Scenario: A later GitHub call after a retried lookup

- **WHEN** the lookup finds a token on its second attempt and `github_token()` is called again
- **THEN** `github_token()` returns the same token and runs no subprocess

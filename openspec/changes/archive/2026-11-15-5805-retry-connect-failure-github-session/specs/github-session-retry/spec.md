# Spec Delta

## REMOVED Requirements

### Requirement: A refused connect is sent once
**Reason**: Issue #5805 establishes that the GitHub session resends a GET after `httpx2.ConnectError` or `httpx2.ConnectTimeout`.
**Migration**: The requirement "A GET is resent after a connect failure" holds the new rule.

## ADDED Requirements

### Requirement: A GET is resent after a connect failure
The GitHub session SHALL send a GET again after `httpx2.ConnectError` or `httpx2.ConnectTimeout`, with jittered backoff, at most `DEFAULT_GH_MAX_RETRIES` more times for each gidgethub attempt, after the same ledger wait.

#### Scenario: A connect timeout on the first listing request
- **WHEN** The first listing request raises `httpx2.ConnectTimeout` and the second answers page 1.
- **THEN** Intake reads the items, the session records two attempts, and the run writes no connect error.

#### Scenario: A connect error on the first attempt
- **WHEN** The first attempt of `GET /user` raises `httpx2.ConnectError` and the second answers with a user.
- **THEN** The session returns the answer, and it has sent `GET /user` twice.

#### Scenario: The connect resends stop at the retry bound
- **WHEN** Each attempt of a GET raises `httpx2.ConnectTimeout`.
- **THEN** The session sends one request and `DEFAULT_GH_MAX_RETRIES` resends for each attempt, and it raises `GitHubUnreadError`.

### Requirement: A write is not resent after a connect failure
The GitHub session MUST NOT send a write again after a connect failure.

#### Scenario: A connect timeout on a POST
- **WHEN** A POST fails with `httpx2.ConnectTimeout`.
- **THEN** The session sends one request and raises `GitHubUnreadError`.

#### Scenario: A connect error on a POST
- **WHEN** A POST fails with `httpx2.ConnectError`.
- **THEN** The session sends one request and raises `GitHubUnreadError`.

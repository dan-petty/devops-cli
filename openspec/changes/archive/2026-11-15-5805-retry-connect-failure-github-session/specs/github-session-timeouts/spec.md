# Spec Delta

## ADDED Requirements

### Requirement: A connect timeout on a GET is resent up to the retry bound
The GitHub session SHALL send a GET again after `httpx2.ConnectTimeout`, at most `DEFAULT_GH_MAX_RETRIES` more times for each attempt. A connect timeout on a write SHALL NOT be resent.

#### Scenario: A connect timeout on a GET resends
- **WHEN** A GET times out on connect.
- **THEN** The session resends the request up to `DEFAULT_GH_MAX_RETRIES` more times.

#### Scenario: A connect timeout on a write does not resend
- **WHEN** A POST times out on connect.
- **THEN** The session raises `GitHubUnreadError` after one request.

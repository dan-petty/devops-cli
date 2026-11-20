## REMOVED Requirements

### Requirement: The GitHub session reads within 60 seconds
**Reason**: Its last scenario held the download of `devops install-tools`, which is gone (#4363).
**Migration**: The requirement below keeps the read bound of the session.

## ADDED Requirements

### Requirement: The GitHub session reads within 60 seconds, with no retry
The GitHub session SHALL wait at most `DEFAULT_GH_SESSION_READ_TIMEOUT_SECONDS` (60 s) for each read of an answer. A read that gets no answer in that time SHALL raise `GitHubUnreadError` naming `ReadTimeout`, and the session SHALL NOT send the request again.

#### Scenario: The session's client reads within 60 seconds
- **WHEN** the session sends `GET /user`
- **THEN** the request has the connect timeout `DEFAULT_GH_SESSION_CONNECT_TIMEOUT_SECONDS` and a read timeout of 60 s

#### Scenario: A host that does not answer
- **GIVEN** a host that takes the request and sends no answer, and a read bound of 0.05 s
- **WHEN** the session sends `GET /user`
- **THEN** it raises `GitHubUnreadError` whose message names `ReadTimeout`
- **AND** it has sent the request once, with no wait for a resend

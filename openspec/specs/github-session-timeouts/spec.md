# github-session-timeouts Specification

## Purpose
The read bound of the GitHub session, the read bound that downloads keep, and the order of the bounds around a GitHub read, so that a read with no answer fails before the call around it stops.

## Requirements

### Requirement: The GitHub session reads within 60 seconds
The GitHub session SHALL wait at most `DEFAULT_GH_SESSION_READ_TIMEOUT_SECONDS` (60 s) for each read of an answer. A read that gets no answer in that time SHALL raise `GitHubUnreadError` naming `ReadTimeout`, and the session SHALL NOT send the request again. A download through the HTTP entry point SHALL keep the read timeout `DEFAULT_HTTP_TIMEOUT_SECONDS`.

#### Scenario: The session's client reads within 60 seconds
- **WHEN** the session sends `GET /user`
- **THEN** the request has the connect timeout `DEFAULT_GH_SESSION_CONNECT_TIMEOUT_SECONDS` and a read timeout of 60 s

#### Scenario: A host that does not answer
- **GIVEN** a host that takes the request and sends no answer, and a read bound of 0.05 s
- **WHEN** the session sends `GET /user`
- **THEN** it raises `GitHubUnreadError` whose message names `ReadTimeout`
- **AND** it has sent the request once, with no wait for a resend

#### Scenario: A download keeps its read timeout
- **WHEN** `devops install-tools` downloads a release archive
- **THEN** the request has the read timeout `DEFAULT_HTTP_TIMEOUT_SECONDS`

### Requirement: Each bound around a GitHub read is shorter than the call around it
In each chain of bounds around a GitHub read, each bound SHALL be shorter than the next one. The chain of the implement job is `DEFAULT_VALKEY_TIMEOUT_SECONDS`, `DEFAULT_GH_SESSION_READ_TIMEOUT_SECONDS` and `DEFAULT_ROADMAP_IMPLEMENT_MONITOR_TIMEOUT_SECONDS`. The chain of a `resource://gh/` resource of the MCP server is `DEFAULT_VALKEY_TIMEOUT_SECONDS`, `DEFAULT_GH_SESSION_READ_TIMEOUT_SECONDS` and `DEFAULT_MCP_TOOL_TIMEOUT_SECONDS`.

#### Scenario: The defaults make a chain
- **WHEN** the test reads the defaults of each chain
- **THEN** each one is shorter than the next one in its chain

#### Scenario: An MCP read of a gh resource waits longer than a session read
- **WHEN** the test reads `DEFAULT_GH_SESSION_READ_TIMEOUT_SECONDS` and `DEFAULT_MCP_TOOL_TIMEOUT_SECONDS`
- **THEN** the session read timeout is shorter than the MCP bound

#### Scenario: An inner bound that is not shorter fails the chain
- **WHEN** the session read timeout is 3,600 s, the same as the watch of the checks
- **THEN** the chain test fails for that pair

## Purpose

The GitHub session's retry of a read whose connection is lost, the write it never sends again, the page of a listing it resends, and the wait each resend takes on the identity's ledger.

## ADDED Requirements

### Requirement: A GET that loses its connection is sent again
The GitHub session SHALL send a GET again when its connection ends or fails before GitHub's answer is read, with `httpx2.RemoteProtocolError`, `httpx2.ReadError` or `httpx2.WriteError`. It SHALL send the GET at most `DEFAULT_GH_MAX_RETRIES` more times for each attempt that gidgethub makes.

#### Scenario: The first attempt loses its connection and the second answers
- **WHEN** GitHub drops the first `GET /user` with `httpx2.RemoteProtocolError`
- **AND** GitHub answers the second attempt with a login
- **THEN** the session returns the answer
- **AND** it has sent `GET /user` twice

#### Scenario: Every attempt loses its connection
- **WHEN** GitHub drops every attempt of `GET /user` with `httpx2.RemoteProtocolError`
- **THEN** the session sends `GET /user` three times
- **AND** it raises `GitHubUnreadError` whose message ends with `: RemoteProtocolError`

### Requirement: A write that loses its connection is sent once
The GitHub session SHALL NOT send a write again when its connection is lost. GitHub may have applied the write. A write that loses its connection SHALL raise `GitHubUnreadError`.

#### Scenario: A POST that loses its connection
- **WHEN** GitHub drops the connection of `POST /user/keys` with `httpx2.RemoteProtocolError`
- **THEN** the session has sent `POST /user/keys` once
- **AND** it raises `GitHubUnreadError`

### Requirement: A listing resends only the page that lost its connection
When a listing loses its connection on a page, the GitHub session SHALL send that page again. It SHALL NOT send the earlier pages again. Each item of the listing SHALL appear once.

#### Scenario: Page 3 loses its connection
- **WHEN** GitHub drops page 3 of a three-page listing with `httpx2.RemoteProtocolError`
- **AND** GitHub answers the second attempt of page 3
- **THEN** the session has sent pages 1, 2, 3 and then page 3 again
- **AND** it returns every item of the three pages once

### Requirement: A refused connect is sent once
The GitHub session SHALL NOT send a GET again when its connect is refused with `httpx2.ConnectError`.

#### Scenario: A GET whose connect is refused
- **WHEN** the connect of `GET /user` is refused with `httpx2.ConnectError`
- **THEN** the session has sent `GET /user` once
- **AND** it raises `GitHubUnreadError`

### Requirement: A resend waits through the identity's ledger
Each resend of a GET that lost its connection SHALL pace on the ledger of the session's identity. It SHALL wait the delay that the ledger gives from `DEFAULT_GH_SERVER_ERROR_RETRY_FLOOR_SECONDS`. The ledger SHALL record each wait as a throttle.

#### Scenario: A lost GET waits on the ledger
- **WHEN** GitHub drops the first `GET /user` with `httpx2.RemoteProtocolError`
- **AND** GitHub answers the second attempt
- **THEN** the session waits one time, for at least `DEFAULT_GH_SERVER_ERROR_RETRY_FLOOR_SECONDS`
- **AND** the ledger of the session's identity records one throttle of that wait

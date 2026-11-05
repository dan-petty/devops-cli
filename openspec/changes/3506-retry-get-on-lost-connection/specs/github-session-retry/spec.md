## Purpose

The GitHub session's retry of a read whose connection is lost, the write it never sends again, the page of a listing it resends, and the wait each resend takes on the identity's ledger.

## ADDED Requirements

### Requirement: A GET that loses its connection is sent again
The GitHub session SHALL send a GET again when the connection ends or fails before GitHub's answer is read, with `httpx2.RemoteProtocolError`, `httpx2.ReadError` or `httpx2.WriteError`. It SHALL send the GET at most `DEFAULT_GH_MAX_RETRIES` times again. When every attempt loses its connection, the session SHALL raise `GitHubUnreadError` with the same message as before this rule.

#### Scenario: The first attempt loses its connection and the second answers
- **WHEN** GitHub drops the connection of the first `GET /user` with `httpx2.RemoteProtocolError`, and answers the second attempt with a login
- **THEN** the session returns the answer, and it has sent `GET /user` twice

#### Scenario: Every attempt loses its connection
- **WHEN** GitHub drops the connection of every attempt of `GET /user` with `httpx2.RemoteProtocolError`
- **THEN** the session sends `GET /user` three times, and it raises `GitHubUnreadError` whose message ends with `: RemoteProtocolError`

### Requirement: A write that loses its connection is sent once
The GitHub session SHALL NOT send a write again when its connection is lost, because GitHub may have applied the write. A write that loses its connection SHALL raise `GitHubUnreadError`.

#### Scenario: A POST that loses its connection
- **WHEN** GitHub drops the connection of `POST /user/keys` with `httpx2.RemoteProtocolError`
- **THEN** the session has sent `POST /user/keys` once, and it raises `GitHubUnreadError`

### Requirement: A listing resends only the page that lost its connection
When a listing loses its connection on a page, the GitHub session SHALL send that page again, and it SHALL NOT send the pages before it again. The items of the listing SHALL each appear once.

#### Scenario: Page 3 loses its connection
- **WHEN** GitHub drops the connection of page 3 of a listing of three pages with `httpx2.RemoteProtocolError`, and answers the second attempt of page 3
- **THEN** the session sends pages 1, 2, 3 and 3 again, and it returns every item of the three pages once

### Requirement: A refused connect is sent once
The GitHub session SHALL NOT send a GET again when its connect is refused with `httpx2.ConnectError`.

#### Scenario: A GET whose connect is refused
- **WHEN** the connect of `GET /user` is refused with `httpx2.ConnectError`
- **THEN** the session has sent `GET /user` once, and it raises `GitHubUnreadError`

### Requirement: A resend waits through the identity's ledger
Each resend of a GET that lost its connection SHALL pace on the ledger of the session's identity, and SHALL wait for the delay the ledger gives from `DEFAULT_GH_SERVER_ERROR_RETRY_FLOOR_SECONDS`. The wait SHALL be recorded on that ledger as a throttle.

#### Scenario: A lost GET waits on the ledger
- **WHEN** GitHub drops the connection of the first `GET /user` with `httpx2.RemoteProtocolError`, and answers the second attempt
- **THEN** the session waits one time, for at least `DEFAULT_GH_SERVER_ERROR_RETRY_FLOOR_SECONDS`, and the ledger of the session's identity records one throttle of that wait

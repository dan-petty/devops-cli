## ADDED Requirements

### Requirement: A mint that GitHub does not answer refuses no identity
An exchange that GitHub answers with a 5xx, or does not answer, SHALL raise `GitHubUnreadError` that names the App's bot login, and the Service SHALL NOT read it as a refused identity. When a renewal fails, the process SHALL use the kept installation token until it expires, and the next call SHALL mint again.

#### Scenario: GitHub does not answer while a lane fetches
- **WHEN** GitHub answers the exchange with HTTP 502 and a lane runs `git fetch origin`
- **THEN** the fetch raises `GitHubUnreadError`, no child starts, and the Service halts no lane

#### Scenario: GitHub does not answer the renewal
- **WHEN** the kept token has 5 minutes left and GitHub answers the renewal with HTTP 502
- **THEN** the next git child gets the kept token, and the call after it mints a new token

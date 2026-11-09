## MODIFIED Requirements

### Requirement: A served_by display shows the server without userinfo
The table of `devops ai cost report --by backend` SHALL show the `host[:port]` of each stored served_by value. `devops review benchmark` SHALL show its host. Both displays SHALL read an absolute URL with httpx2 and a bare `host[:port]` with the shared URL-or-authority reader. Both SHALL show `unknown` for a value that neither reader accepts, and SHALL never show the stored text.

#### Scenario: A stored served_by URL with a password
- **WHEN** the ledger holds a gateway call whose served_by is `http://user:pw@example.com:11434`
- **THEN** the table of `devops ai cost report --by backend` shows the serving backend `example.com:11434`

#### Scenario: A stored bare authority
- **WHEN** the ledger holds a gateway call whose served_by is `example.com:11434`
- **THEN** the table of `devops ai cost report --by backend` shows the serving backend `example.com:11434`

#### Scenario: A stored value that names no server
- **WHEN** the ledger holds a gateway call whose served_by is `example.com:`
- **THEN** the table of `devops ai cost report --by backend` shows the serving backend `unknown`

#### Scenario: A stored URL that urlsplit cannot read
- **WHEN** the ledger holds a gateway call whose served_by is `http://[::1`
- **THEN** `devops ai cost report --by backend` exits 0 and the table shows the serving backend `unknown`

#### Scenario: A bare authority with userinfo in the review benchmark
- **WHEN** the review benchmark labels the backend `u:pw@example.com:11434`
- **THEN** the label is `example.com`

## ADDED Requirements

### Requirement: A stored serving backend that no URL reader accepts is hosted
`is_local` SHALL decide the locality of a call from the stored served_by value, and SHALL NOT raise for a value that `urllib.parse.urlsplit` cannot read. Such a value names no local server, so the call SHALL count as hosted. A list of served_by values SHALL be local only when every value in it is local. A readable served_by value SHALL keep its classification.

#### Scenario: A stored served_by that urlsplit cannot read
- **WHEN** `is_local` runs for a gateway call whose served_by is `http://[::1`
- **THEN** it returns false and raises no `ValueError`

#### Scenario: A list that holds one unreadable value
- **WHEN** `is_local` runs for a gateway call whose served_by is `http://localhost:11434,http://[::1`
- **THEN** it returns false and raises no `ValueError`

#### Scenario: A stored local URL
- **WHEN** `is_local` runs for a gateway call whose served_by is `http://localhost:11434`
- **THEN** it returns true
- **AND** `devops ai cost report --by backend` shows the serving backend `localhost:11434`

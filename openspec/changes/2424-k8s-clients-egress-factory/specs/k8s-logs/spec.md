## ADDED Requirements

### Requirement: The Loki client looks up its host one time for each query
A Loki query SHALL resolve the host of the Loki URL one time, at the connect, and SHALL make no lookup before it. A Loki URL whose scheme is not `http` or `https` SHALL fail with no lookup.

#### Scenario: One Loki query
- **WHEN** a LogQL query runs against `http://example.com:3100`
- **THEN** `example.com` is looked up one time, and the socket gets the address of that lookup

#### Scenario: A Loki URL that is not HTTP
- **WHEN** a LogQL query runs against `ftp://example.com:3100`
- **THEN** the query fails with `httpx2.UnsupportedProtocol` and `example.com` is not looked up

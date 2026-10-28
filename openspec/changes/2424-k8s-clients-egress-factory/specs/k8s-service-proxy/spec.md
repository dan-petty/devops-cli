## ADDED Requirements

### Requirement: A direct service URL looks up its host one time for each request
A request of `get_json` to a direct URL, not a `k8s://` address, SHALL resolve the host one time, at the connect, at the private level, and SHALL make no lookup before it.

#### Scenario: One request to a direct URL
- **WHEN** `get_json("http://example.com:9090", "api/v1/query")` runs
- **THEN** `example.com` is looked up one time, and the socket gets the address of that lookup

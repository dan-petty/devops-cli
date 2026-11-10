## MODIFIED Requirements

### Requirement: A Qdrant server shows as host and port
The label of a Qdrant address SHALL be `host[:port]` for an `http` or `https` URL, with no scheme, no userinfo and no path. The label of a `k8s://` or `k8s+https://` Service address SHALL be `<service>.<namespace>`, followed by `:<port>` when the port is a number. The label of a text with no origin, of a Service address that names no Service, and of a port outside the range 0 to 65535 SHALL be `unknown`.

#### Scenario: A URL with userinfo and a path
- **WHEN** the address is `http://user:secret@example.com:6333/prefix/path`
- **THEN** the label is `example.com:6333`

#### Scenario: A Service address
- **WHEN** the address is `k8s+https://user:secret@devops/qdrant:6333/prefix/path?q=secret`
- **THEN** the label is `qdrant.devops:6333`

#### Scenario: A text with no origin
- **WHEN** the address is `user:secret@example.com:6333/prefix`
- **THEN** the label is `unknown`

#### Scenario: A port that no server can have
- **WHEN** the address is `http://example.com:99999`
- **THEN** the label is `unknown`

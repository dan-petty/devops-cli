## MODIFIED Requirements

### Requirement: The upsert span names a cluster Service by its DNS name
When the Qdrant address is a `k8s://` or `k8s+https://` Service address, the `qdrant.upsert_points` span SHALL set `server.address` to `<service>.<namespace>`. It SHALL set `server.port` to the port of the address when the port is a number, and SHALL set no `server.port` when the port is a name. The span SHALL hold no userinfo, path or query of the address. When `parse_service_url` refuses the address, the span SHALL set `server.address` to `unknown` and SHALL NOT raise `ServiceAddressError`.

#### Scenario: A Service address
- **WHEN** `qdrant.url` is `k8s://devops/qdrant:6333` and `upsert_points` runs
- **THEN** `server.address` is `qdrant.devops` and `server.port` is 6333

#### Scenario: A Service address with userinfo, a path and a query
- **WHEN** `qdrant.url` is `k8s+https://user:secret@devops/qdrant:6333/path?q=secret` and `upsert_points` runs
- **THEN** `server.address` is `qdrant.devops` and `server.port` is 6333
- **AND** no attribute of the span holds `secret`

#### Scenario: A Service address with a named port
- **WHEN** `qdrant.url` is `k8s://devops/qdrant:http` and `upsert_points` runs
- **THEN** `server.address` is `qdrant.devops` and the span has no `server.port`

#### Scenario: A malformed Service address
- **WHEN** `qdrant.url` is `k8s://devops` and `upsert_points` runs
- **THEN** `server.address` is `unknown` and the span holds no `server.port`

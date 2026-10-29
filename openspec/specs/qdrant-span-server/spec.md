# qdrant-span-server Specification

## Purpose
How the spans of the Qdrant client name their server. The name is the host and the port of the configured address, so the userinfo and the path of the URL never get into an exported span.

## Requirements

### Requirement: The upsert span names its server by host and port
The `qdrant.upsert_points` span SHALL set `server.address` to the host of the origin of the Qdrant URL and `server.port` to its port. The port SHALL be the default port of the scheme when the URL has none. The span SHALL hold no scheme, no userinfo and no path of the URL. The client SHALL still send the userinfo to the server.

#### Scenario: A URL with userinfo and a path
- **WHEN** `qdrant.url` is `http://user:secret@example.com:6333/prefix/path` and `upsert_points` runs
- **THEN** `server.address` is `example.com` and `server.port` is 6333
- **AND** no attribute of the span holds `secret`, `user` or `/prefix`

#### Scenario: A URL with a port
- **WHEN** `qdrant.url` is `http://example.com:6333` and `upsert_points` runs
- **THEN** `server.address` is `example.com` and `server.port` is 6333

#### Scenario: A URL with a user name alone and no port
- **WHEN** `qdrant.url` is `https://token@example.com` and `upsert_points` runs
- **THEN** `server.address` is `example.com` and `server.port` is 443
- **AND** no attribute of the span holds `token`

### Requirement: The upsert span names a cluster Service by its DNS name
When the Qdrant address is a `k8s://` or `k8s+https://` Service address, the `qdrant.upsert_points` span SHALL set `server.address` to `<service>.<namespace>`. It SHALL set `server.port` to the port of the address when the port is a number, and SHALL set no `server.port` when the port is a name. The span SHALL hold no userinfo, path or query of the address.

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

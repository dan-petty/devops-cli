# qdrant-server-label Specification

## Purpose
How the log lines, errors and cache keys of the Qdrant client name their server. The name is the host and the port of the configured address, so the userinfo and the path of the URL never get into a log, an error or a key.

## Requirements

### Requirement: A Qdrant server shows as host and port
The label of a Qdrant address SHALL be `host[:port]` for an `http` or `https` URL, with no scheme, no userinfo and no path. The label of a `k8s://` or `k8s+https://` Service address SHALL be `<service>.<namespace>`, followed by `:<port>` when the port is a number. The label of a text with no origin, and of a Service address that names no Service, SHALL be `unknown`.

#### Scenario: A URL with userinfo and a path
- **WHEN** the address is `http://user:secret@example.com:6333/prefix/path`
- **THEN** the label is `example.com:6333`

#### Scenario: A Service address
- **WHEN** the address is `k8s+https://user:secret@devops/qdrant:6333/prefix/path?q=secret`
- **THEN** the label is `qdrant.devops:6333`

#### Scenario: A text with no origin
- **WHEN** the address is `user:secret@example.com:6333/prefix`
- **THEN** the label is `unknown`

### Requirement: Log lines name the server by its label
The debug line of `QdrantClient.list_collections` for a failure, and the debug line of the RAG investigator for an unreachable Qdrant server, SHALL name the server by its label. They SHALL hold no userinfo and no path.

#### Scenario: The list of collections fails
- **WHEN** `qdrant.url` is `http://user:secret@example.com:6333/prefix/path` and `list_collections` fails
- **THEN** the log line is `Failed to list Qdrant collections from example.com:6333: <error>`

#### Scenario: The investigator finds the server unreachable
- **WHEN** `qdrant.url` is `http://user:secret@example.com:6333/prefix/path` and the server does not answer
- **THEN** the log line is `Qdrant vector store unreachable at example.com:6333, skipping RAG investigation`

### Requirement: An invalid URL error never holds the URL
`InvalidURLError` SHALL hold no userinfo, no path and no URL text in its message and in `details["url"]`. The errors of `QdrantClient` and of `validate_configured_service_url` for an invalid address SHALL hold no userinfo and no path.

#### Scenario: A URL with no scheme
- **WHEN** `qdrant.url` is `user:secret@example.com:6333/prefix/path`
- **THEN** the message is `Invalid URL: missing scheme or host in qdrant.url`
- **AND** the message and `details` hold no `secret`, no `user` and no `prefix`

#### Scenario: A URL with a scheme that the client refuses
- **WHEN** `qdrant.url` is `ftp://user:secret@example.com:6333/prefix/path`
- **THEN** the message is `Invalid URL for server example.com:6333: Invalid Qdrant URL scheme 'ftp': must be http or https`
- **AND** the message and `details` hold no `secret`, no `user`, no `prefix` and no `://`

### Requirement: An invalid URL error names its server or the kind of problem
When the URL has an origin, the message of `InvalidURLError` SHALL be `Invalid URL for server <label>: <reason>`. When it has none, the message SHALL be `Invalid URL: <reason>`, so the label `unknown` never reads as a URL. The reason SHALL tell the kind of problem. The reason of `QdrantClient` for an address with no scheme or host SHALL name the setting `qdrant.url`.

#### Scenario: An address with no scheme or host names the setting
- **WHEN** `qdrant.url` is `localhost:6333`
- **THEN** the message is `Invalid URL: missing scheme or host in qdrant.url`

#### Scenario: The broker refuses a scheme
- **WHEN** a request for `file:///etc/passwd` reaches the HTTP broker
- **THEN** the message is `Invalid URL: Only http and https URLs may be requested`

### Requirement: The search cache key tells servers apart without holding the URL
The in-memory key that records a verified collection SHALL hold the label of the server, the SHA-256 digest of the whole base URL, and the collection name. It SHALL NOT hold the URL. Two servers whose labels are equal SHALL have two keys when their base URLs differ.

#### Scenario: A URL with userinfo
- **WHEN** a collection is verified for a client with `qdrant.url` `http://user:secret@example.com:6333/prefix/path`
- **THEN** the key is `("example.com:6333", <digest of the base URL>, <collection>)`
- **AND** the key holds no `secret`, no `user` and no `prefix`

#### Scenario: Servers that differ in scheme or path prefix
- **WHEN** a collection is verified for `http://example.com` and for `https://example.com`, or for `http://example.com/qdrant-a` and for `http://example.com/qdrant-b`
- **THEN** each server has its own key, and the model of the second server is checked against its own recorded model

#### Scenario: Addresses with the label unknown
- **WHEN** two clients have different base URLs and the label `unknown`
- **THEN** each has its own key

## ADDED Requirements

### Requirement: A URL error text never holds the configured URL
The reason text of `normalize_ollama_base_url`, the error text of `_parse_and_validate_scheme`, and each error message and log line of `QdrantClient` that holds an exception SHALL NOT hold the configured URL, its userinfo or its path. `QdrantClient` SHALL replace each URL in an exception text with the label of its server.

#### Scenario: An Ollama URL with no host
- **WHEN** `normalize_ollama_base_url` runs with `http:///prefix/secret`
- **THEN** the raised `InvalidURLError` text holds `missing host or authority` and holds neither `http:///prefix/secret` nor `prefix` nor `secret`

#### Scenario: A service URL with no hostname
- **WHEN** `_parse_and_validate_scheme` runs with `http:///prefix/secret`
- **THEN** the raised error text holds `missing valid hostname` and holds neither `http:///prefix/secret` nor `prefix` nor `secret`

#### Scenario: A Qdrant error text that holds the request URL
- **WHEN** a native call of `QdrantClient.list_collections` fails with an exception whose text holds `http://user:secret@example.com:6333/prefix/path`
- **THEN** the `QdrantClientError` text and the debug log line hold `example.com:6333` and hold no `user`, no `secret`, no `prefix`, no `path` and no `://`

# Proposal

## Why

Issue #2709: four places in the RAG module and one error class name the Qdrant server by the whole configured URL.

- The URL in `qdrant.url` can hold userinfo, which the client sends as Basic authentication, and a path.
- #2459 made the `qdrant.upsert_points` span name its server by host and port. Four sites still write the URL.
- `QdrantClient.list_collections` writes `self.base_url` in a debug log line.
- The investigator writes the configured `qdrant.url` in its "unreachable" debug line.
- `InvalidURLError` writes its URL in its message and in `details["url"]`. The Qdrant client raises it, and so does `validate_configured_service_url`.
- `_verify_single_collection_for_search` keys its in-memory cache with `str(qdrant.base_url)`.

Userinfo is valid configuration, so the change keeps it in the request and out of every text that the client writes.

## What Changes

- New `qdrant_server_label(url)` in `ai/rag/qdrant.py`, and `QdrantClient.server_label`, which uses it for `self.base_url`.
  - An `http` or `https` URL shows as `server_label` (`ai/benchmark/labels.py`, #2481) shows it: `host[:port]`.
  - A `k8s://` address shows as `<service>.<namespace>`, with `:<port>` when the port is a number.
  - A text with no origin, and a `k8s://` address that names no Service, show as `unknown`.
- The `list_collections` log line, the investigator log line and the retriever cache key use `server_label`.
- The retriever cache key holds the label and a SHA-256 digest of the whole base URL. The label drops the scheme, the path and a default port, so two servers can share it. The digest tells them apart.
- `InvalidURLError` names its server with `server_label`, in its message and in `details["url"]`: `Invalid URL for server <label>: <reason>`. A URL with no origin gives `Invalid URL: <reason>`, so `unknown` never reads as a URL. This covers the Qdrant `__init__` error and the errors of `validate_url`, and it covers every other raiser of the class. The reason keeps the kind of problem. The Qdrant `__init__` reason names `qdrant.url`.
- Two reason texts of `validate_url` and `_validate_dns_name_syntax` no longer repeat the URL.
- The change alters observable text, so it has the spec delta `qdrant-server-label`. It fits one pull request.

## Capabilities

### New Capabilities

- `qdrant-server-label`: how the log lines, errors and cache keys of the Qdrant client name their server.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/ai/rag/qdrant.py`, `investigator.py`, `retriever.py`.
- `src/devops_cli/exceptions/validation.py`, `src/devops_cli/core/validation.py`.
- `tests/test_rag_qdrant_server_label.py`.

## Feasibility

- The leak is real on `origin/main` at `a3453463`. With `http://user:secret@127.0.0.1:1/prefix/path`, `list_collections` writes `Failed to list Qdrant collections from http://user:secret@127.0.0.1:1/prefix/path: ...` to the debug log. The new tests read the log records and the error text.
- `validate_configured_service_url` does not name the server by host and port. The base `DevOpsCLIError` masks secrets in the message and in `details`, so the password and the user name show as `<masked-user>:<masked-password>`. The path stays. A URL with no scheme, such as `user:secret@example.com:6333/prefix`, has no URL syntax that the masker can read, so `InvalidURLError` shows it in full, in its message and in `details["url"]`. `validate_url` also repeats the URL in two reason texts.
- `SSRFBlockedError` already shows `scheme://<masked>:port/path`. It holds no userinfo and is outside this issue.
- `get_url_origin("user:secret@example.com:6333")` is `None`, because httpx2 reads `user` as a scheme. `server_label` then gives `unknown`. `get_url_origin("k8s://devops/qdrant:6333")` is the namespace with no port, so a `k8s://` address needs `parse_service_url`, as in #2459.
- The retriever cache key stays in memory. `_SEARCH_VERIFIED_MODELS` has no reader other than `_verify_single_collection_for_search` and `reset_search_verified_models`, so no export or log shows it.

## Existing Tool Considered

`server_label` (#2481) composes `get_url_origin` (#1112) and `origin_label` (#1110). httpx2 reads the origin, and its origin never holds userinfo. `parse_service_url` reads a Service address. The change builds no parser: `qdrant_server_label` is one branch for the `k8s://` form that calls these helpers. It deletes the four uses of the whole URL and the URL text in `InvalidURLError`.

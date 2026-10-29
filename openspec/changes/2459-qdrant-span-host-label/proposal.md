# Proposal

## Why

Issue #2459: the `qdrant.upsert_points` span writes the configured Qdrant URL as `server.address`.

- `QdrantClient.__init__` keeps the URL with `urlunparse(parsed)`. `self.base_url` keeps its scheme, its path and its userinfo.
- `upsert_points` sets `server.address` to `str(self.base_url)`. The OpenTelemetry conventions define `server.address` as a host and `server.port` as a port.
- A password in `qdrant.url` goes to every exported span. The span has no `server.port`.
- #1110 fixed the same defect for the AI URLs. It takes the span server from the httpx2 origin of the URL.

Userinfo is valid configuration, so the change keeps it in the request and out of the span.

## What Changes

- The `qdrant.upsert_points` span takes `server.address` and `server.port` from one method of `QdrantClient`, `_server_span_attributes`.
- For an `http` or `https` URL, the method calls `origin_span_attributes(get_url_origin(base_url))`. These are the helpers of #1110 and #1112. The span gets the host and the port of the origin, with the default port of the scheme when the URL has none.
- For a `k8s://` or `k8s+https://` address, the method reads the address with `parse_service_url`. The span gets the in-cluster DNS name of the Service, `<service>.<namespace>`, as `server.address`. It gets the port as `server.port` when the port is a number. A named port gives no `server.port`.
- A URL with no httpx2 origin gives a span with neither attribute.
- The span has an observable attribute change, so the change has the spec delta `qdrant-span-server`.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `qdrant-span-server`: how the spans of the Qdrant client name their server.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/ai/rag/qdrant.py`.
- `tests/test_rag_qdrant_span.py`.

## Feasibility

- The leak is real on `origin/main` at `9e8317bb`. The new test configures `http://user:secret@example.com:6333/prefix/path`, upserts one point and reads the exported span. `server.address` is the whole URL, and the span has no `server.port`.
- httpx2 2.13.1 gives `httpx2.URL("http://user:pw@example.com:6333/prefix").origin == Origin(scheme='http', host='example.com', port=6333)` and, for `https://example.com`, port 443.
- The k8s case in the issue does not hold as written. The issue names `k8s://qdrant.devops:6333`. The real address form is `k8s://<namespace>/<service>:<port>[/path]` (`parse_service_url`, `src/devops_cli/k8s/service_proxy.py`), and `parse_service_url` refuses the issue's form with "missing a service name". For `k8s://devops/qdrant:6333`, `httpx2.URL(...).origin` is `Origin(scheme='k8s', host='devops', port=None)`. That is the namespace, with no Service and no port. So `origin_span_attributes` alone gives a wrong name for a Service address. The change reads a Service address with `parse_service_url` and writes the DNS name `qdrant.devops` that the issue's example shows.
- `parse_service_url` reads the host with `urlparse(...).hostname`, so it never returns userinfo, and a `k8s://user:pw@devops/qdrant:6333` address gives the same span as one with no userinfo. A port can be a name (`qdrant:http`), so `server.port` is set only for a number.
- The `ai.rag.qdrant_search` span, the other span of the client, sets no `server.*` attribute. Only `qdrant.upsert_points` has the defect.

## Existing Tool Considered

httpx2 is the HTTP client of the project. Its `URL.origin` gives the scheme, host and port and never the userinfo. `origin_span_attributes` (#1110) writes the two span attributes of an origin, and `get_url_origin` (#1112) reads a URL to its origin. `parse_service_url` reads a Service address. The change builds no parser. It deletes the `str(self.base_url)` attribute.

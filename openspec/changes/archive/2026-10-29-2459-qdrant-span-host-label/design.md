# Design

## Decisions

- **One method names the server of the client.** `QdrantClient._server_span_attributes()` returns the `server.address` and `server.port` attributes for `self.base_url`. `upsert_points` spreads them into the span attributes. The attribute is set where the span is built, so no later reader of the span can see the URL.
- **An HTTP URL uses the helpers of #1110.** `origin_span_attributes(get_url_origin(self.base_url))` gives the host and the port of the origin that httpx2 sends to. A URL with no origin gives `{}`, as for the AI spans.
- **A Service address uses `parse_service_url`.** The origin of a `k8s://` URL is the namespace with no port. The span names the target of the client, which is the Service, so it writes `<service>.<namespace>` (the in-cluster DNS name) and the numeric port. The port of a Service can be a name, which is not a number, so then the span has no `server.port`.
- **The span does not resolve the proxy.** The API server of the kubeconfig is how the client reaches the Service, not the Qdrant target. Reading it needs a kubeconfig read per span.

## Rejected alternatives

- **`origin_span_attributes` for every URL.** For `k8s://devops/qdrant:6333` it writes the namespace `devops` and no port. The probe in the proposal shows this.
- **The k8s address form of the issue (`k8s://qdrant.devops:6333`).** `parse_service_url` refuses it, and `QdrantClient` would fail at the first request.
- **Omit the attributes for a Service address.** The span would lose the target. The Service name and port are not secret.
- **A new URL parser in `rag/qdrant.py`.** `parse_service_url`, `get_url_origin` and `origin_span_attributes` cover both forms.

## Non-goals

- Log lines of `qdrant.py`, `investigator.py` and the retriever cache key carry `base_url`. They are not span attributes, so the issue does not cover them.

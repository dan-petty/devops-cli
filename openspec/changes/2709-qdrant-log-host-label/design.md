# Design

## Decisions

- **One label function for the Qdrant client.** `qdrant_server_label(url)` is in `ai/rag/qdrant.py`, the only module that reads a Qdrant address. `QdrantClient.server_label` applies it to `base_url`. The investigator and the retriever read the property, so no caller formats a URL.
- **An HTTP URL uses `server_label` of #2481.** It already gives `host[:port]` and `unknown`. The RAG module imports it inside the function, as the module does for its other helpers.
- **A Service address uses `parse_service_url`.** The text is `<service>.<namespace>`, as the #2459 span writes `server.address`. A numeric port is added as `:<port>`, as for an HTTP URL, so two ports of one Service keep two cache keys. A named port gives no suffix. `ServiceAddressError` gives `unknown`: a label never raises, and the address text is not shown.
- **`InvalidURLError` is fixed at the class.** The cause is one place: the class writes its URL argument. Each raiser, in `validate_url` and in the clients, passes the URL it holds. The class now writes `server_label(url)` in the message and in `details["url"]`. A raiser needs no change, and a new raiser cannot leak.
- **The reason texts stop repeating the URL.** `validate_url` and `_validate_dns_name_syntax` wrote `'{url}'` in a reason. The class names the server already, so the reason drops it. The hostname text stays, because a host holds no userinfo.

## Rejected alternatives

- **Pass a label from `QdrantClient.__init__` to `InvalidURLError`.** `validate_url` raises the same class with the full URL, and the probe in the proposal shows the path in its text.
- **`mask_uri_credentials` for the log lines.** It masks the password only. A user name alone and the path stay in the text.
- **A label helper in `ai/client/models.py`.** `origin_label` takes an origin, not a URL string.
- **A shared label module for the `k8s://` form.** The Qdrant client is the only reader of that form here.

## Non-goals

- `OllamaClient` writes its URL in a reason text (`ai/models/ollama.py`), and `_parse_and_validate_scheme` writes it in a `missing valid hostname` text. The class change masks the URL argument of each, and the reason text is a separate site, outside this issue.

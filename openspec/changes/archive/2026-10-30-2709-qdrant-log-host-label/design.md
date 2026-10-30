# Design

## Decisions

- **One label function for the Qdrant client.** `qdrant_server_label(url)` is in `ai/rag/qdrant.py`, the only module that reads a Qdrant address. `QdrantClient.server_label` applies it to `base_url`. The investigator and the retriever read the property, so no caller formats a URL.
- **An HTTP URL uses `server_label` of #2481.** It already gives `host[:port]` and `unknown`. The RAG module imports it inside the function, as the module does for its other helpers.
- **A Service address uses `parse_service_url`.** The text is `<service>.<namespace>`, as the #2459 span writes `server.address`. A numeric port is added as `:<port>`, as for an HTTP URL, so two ports of one Service keep two cache keys. A named port gives no suffix. `ServiceAddressError` gives `unknown`: a label never raises, and the address text is not shown.
- **`InvalidURLError` is fixed at the class.** The cause is one place: the class writes its URL argument. Each raiser, in `validate_url` and in the clients, passes the URL it holds. The class now writes `server_label(url)` in the message and in `details["url"]`. A raiser needs no change, and a new raiser cannot leak.
- **The message tells the kind of problem when there is no server to name.** `Invalid URL for server <label>: <reason>` for a URL with an origin, and `Invalid URL: <reason>` for one with none. The quoted `'unknown'` looked like a URL and hid the problem. Each raiser already writes a reason that tells the kind (`Only http and https URLs may be requested`, `Invalid Ollama URL scheme ...`), so the class change loses no hint for the Ollama and broker raisers. The class never names a scheme, because a text such as `user:secret@host` reads with `user` as its scheme. The Qdrant `__init__` reason names `qdrant.url`.
- **The cache key holds the label and a digest of the whole base URL.** The label drops the scheme, the path and a default port, so `http://example.com` and `https://example.com` would share a key, and the model check of the second server would be skipped or compared with a wrong value. The key is `(label, sha256(base_url), collection)`. The digest is in memory only and is never logged.
- **The reason texts stop repeating the URL.** `validate_url` and `_validate_dns_name_syntax` wrote `'{url}'` in a reason. The class names the server already, so the reason drops it. The hostname text stays, because a host holds no userinfo.

## Rejected alternatives

- **Pass a label from `QdrantClient.__init__` to `InvalidURLError`.** `validate_url` raises the same class with the full URL, and the probe in the proposal shows the path in its text.
- **`mask_uri_credentials` for the log lines.** It masks the password only. A user name alone and the path stay in the text.
- **A label helper in `ai/client/models.py`.** `origin_label` takes an origin, not a URL string.
- **A shared label module for the `k8s://` form.** The Qdrant client is the only reader of that form here.

- **The label alone as the key.** The review showed two servers with one label (scheme and path prefix).
- **The label of a `k8s://` URL in `InvalidURLError`.** `server_label` reads the namespace as the host. No Service address reaches this class from the Qdrant client, and a new Service-aware label in the shared class has no other reader.

## Non-goals

- `OllamaClient` writes its URL in a reason text (`ai/models/ollama.py`), and `_parse_and_validate_scheme` writes it in a `missing valid hostname` text. The class change masks the URL argument of each, and the reason text is a separate site, outside this issue.

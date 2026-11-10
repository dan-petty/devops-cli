# Design

## Decisions

- **One helper replaces each URL in an error text.** `_error_text(exc)` in `ai/rag/qdrant.py` finds each URL candidate with `CONST_URL_CANDIDATE_RE` and replaces it with `qdrant_server_label` of that candidate. Every `QdrantClientError` message and every log line that holds `exc` calls it, so a new message cannot leak a URL. The retry warning calls it too.
- **The label checks the port, not the URL parser.** `server_label` in `ai/benchmark/labels.py` returns `unknown` when the origin port is outside 0 to 65535. `qdrant_server_label` delegates to `server_label` for an HTTP URL, so one check covers both labels and every other reader of a server label.
- **The span catches `ServiceAddressError`.** `_server_span_attributes` returns `{"server.address": "unknown"}` for a Service address that `parse_service_url` refuses, as `qdrant_server_label` returns `unknown` for the same address. The span never raises, and the two agree.
- **The reason texts state the problem alone.** `normalize_ollama_base_url` writes `Invalid Ollama URL: missing host or authority`, and `_parse_and_validate_scheme` writes `Invalid <purpose> URL: missing valid hostname`. Neither repeats the URL, which `InvalidURLError` already reduces to its label.

## Rejected alternatives

- **Refuse an out-of-range port in `get_url_origin`.** It would also drop the port of a span and change every caller of the helper, not only the labels that the issue names.
- **Use `redact_text` on the error text.** The probe of the sanitizer shows it masks the userinfo only and keeps the path, so it does not meet the requirement that the address text is not shown.
- **Let `_server_span_attributes` raise `ServiceAddressError`.** `qdrant_server_label` gives `unknown` for the same address, so the span and the label would disagree, which is the defect.
- **Write only the exception class in an error text.** The text of a native error names the fault, such as a refused connection, and a user needs it. Replacing the URL keeps the fault and drops the address.

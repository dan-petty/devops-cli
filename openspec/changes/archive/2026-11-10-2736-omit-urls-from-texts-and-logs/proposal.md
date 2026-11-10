# Proposal: #2736

## Why

Five sites still show a configured URL in an error text, a log line or a span, or read a Service address with a rule that disagrees with the server label. The design of #2709 sets the rule: a label never raises, and the address text is not shown. Each site breaks that rule, so a user can see a userinfo or a path, and the span and the label of one address can disagree. Fixes #2736.

## What Changes

- `normalize_ollama_base_url` SHALL NOT write the configured URL in the reason text of an address with no host or authority.
- `_parse_and_validate_scheme` SHALL NOT write the configured URL in the error text of a URL with no hostname.
- `QdrantClient` SHALL replace each URL in the text of a native or httpx error with the label of its server, in an error message and in a log line.
- `QdrantClient._server_span_attributes` SHALL give `server.address` `unknown` for a malformed Service address, as `qdrant_server_label` gives `unknown`, and SHALL NOT raise `ServiceAddressError`.
- `server_label` and `qdrant_server_label` SHALL give `unknown` for a port outside the range 0 to 65535.

The change touches no command and no option, so it changes no generated documentation.

## Capabilities

- `configured-service-urls`: a URL error text never holds the configured URL.
- `qdrant-server-label`: the label refuses a port that no server can have.
- `qdrant-span-server`: the span of a malformed Service address matches the label.

## Impact

The change is internal to `src/devops_cli`. A user sees a shorter error text with no configured URL. A span of a malformed Service address holds `server.address` `unknown` instead of failing the upsert. Two servers whose address differs only in an out-of-range port share the label `unknown`, as they already share it for an address with no origin.

## Feasibility

The premise was confirmed against the code at `origin/main` `40d2b371` and against the installed libraries:

- `uv run python` with `httpx2` showed that `httpx2.URL("http://example.com:99999").origin` gives `Origin(..., port=99999)`, so `server_label` prints `example.com:99999`. The same probe showed that `parse_service_url("k8s://devops")` raises `ServiceAddressError("missing a service name")` while `qdrant_server_label("k8s://devops")` gives `unknown`.
- `uv run python` with `qdrant_client` showed that a connection error is a `ResponseHandlingException` whose text is `[Errno 111] Connection refused` and whose `source.request.url` holds `http://127.0.0.1:<port>/prefix/path/collections`. The current text holds no URL, but the exception holds one, and no code stops a later library version or another transport error from writing it.
- `rg` found the two reason texts in `ai/models/ollama.py` and `core/validation.py`, and the labels in `ai/benchmark/labels.py` and `ai/rag/qdrant.py`.

The change fits one pull request.

## Existing Tool Considered

No open, maintained tool fixes the error texts and the label rules of this project's own code. `redact_text` of the project masks only userinfo of a URL and keeps its path, so it does not meet the rule that the address text is not shown. The cost to build the change is the tokens of four test cases and five code sites in four files, plus the tokens to keep and fix it until it matches the tool, which is zero: no outside dependency changes. The elapsed time is about one hour.

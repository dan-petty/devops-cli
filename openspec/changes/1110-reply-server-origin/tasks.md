# Tasks

## 1. A reply names its server by the origin of the URL that the client called

- [x] Add failing tests: a chat call to each URL of the issue table gives the `backend_info`, the ledger `server`, the counter `server` label and the span `server.address` and `server.port` of the table; a URL with a password sends Basic authentication and leaves no `pw` in any record; a stream over two Ollama URLs records the leased server without its password; a configured URL with no origin shows `unknown`; the span takes its server from the reply origin, else from the one configured origin
  - Verification: `uv run devops ci test tests/ai/client/test_reply_server.py tests/test_ai_client_telemetry.py tests/test_telemetry.py`
- [x] Add `LLMResponse.origin`, `authority_label` and `origin_label`; set the origin in the Ollama, OpenAI-compatible and Claude paths; get the configured origins of `LLMClient` once; take the ledger `server`, the counter label and the span `server.*` from an origin; keep the origin of the leased server in `network.stream_server`; delete `_extract_server_from_backend_info`, `_server_span_attributes` and the `urlparse(...).netloc` reads
  - Verification: `uv run devops ci test tests/ai/client/test_reply_server.py tests/test_ai_client_telemetry.py tests/test_telemetry.py tests/test_ai_streaming.py tests/test_ai_gateway.py tests/test_ai_gateway_base_url.py tests/test_ai_client_providers_and_embeddings.py`
- [x] Say in `docs/TELEMETRY.md`, through `src/devops_cli/docs/generator.py`, that the span server comes from the URL origin and holds the default port of the scheme
  - Verification: `uv run devops docs generate --sync-readme`

## 2. An embedding request names its server by the origin of its endpoint

- [x] Add a failing test: an Ollama embedding batch to a URL with a password writes the ledger `server` `example.com:11434`, the counter label `example.com:11434` and the span `server.address` `example.com` with `server.port` 11434
  - Verification: `uv run devops ci test tests/test_rag_embeddings.py`
- [x] Take the ledger `server`, the `backend_info` and the batch span `server.*` of an embedding request from the origin of its endpoint, and delete the `urlsplit(endpoint).netloc` read
  - Verification: `uv run devops ci test tests/test_rag_embeddings.py`

## 3. The served_by displays show the server without userinfo

- [x] Add failing tests: `devops ai cost report --by backend` shows `example.com:11434` for `http://user:pw@example.com:11434` and for `example.com:11434`, and `unknown` for `example.com:`; the review benchmark shows `example.com` for `u:pw@example.com:11434` and `unknown` for `example.com:`
  - Verification: `uv run devops ci test tests/test_ai_served_by.py tests/test_review_profile.py`
- [x] Add `served_by_authority` next to the label helper, show its label in the cost report and its host in the review benchmark, and delete the `urlparse` and `urlsplit` reads of served_by
  - Verification: `uv run devops ci test tests/test_ai_served_by.py tests/test_review_profile.py`

## 4. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 1110-reply-server-origin`

## Workflow follow-up

- Pending a person: if `ai.ollama_urls`, `ai.gateway_url` or `ai.api_base_url` held `user:password` before this change, change that password, then run `devops ai cost reset` and `devops ai cache clear`. Ledger rows, response-cache entries and exported counter series from before this change hold it.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

# Proposal

## Why

Issue #1110: the AI client names the server of a reply with display text, and that text keeps the userinfo of the configured URL.

- Each provider turns its base URL into `"<type> (<host>)"` text with `urlparse(...).netloc`. `netloc` keeps `user:password@`.
- The client then reads the host back out of that text. `_extract_server_from_backend_info` cuts the text at the parentheses, and `_server_span_attributes` splits the result again with `urlsplit`.
- Thus a password in `ai.ollama_urls`, `ai.gateway_url` or `ai.api_base_url` goes to the terminal output of `devops ai`, `devops analyze` and the review. It also goes to the spend ledger (`server` and `backend_info`) and to the `server` label of the AI counters. The `llm_response_received` span event and the response cache hold it too.
- A streamed Ollama call records the leased server as `urlparse(leased_url).netloc`, and an embedding request records `urlsplit(endpoint).netloc` and puts the full base URL in `server.address`. Both keep the userinfo too.
- `devops ai cost report --by backend` and `devops review benchmark` show a stored served_by value as text when they cannot read it. The review benchmark shows a bare `user:password@host:port` value whole.
- The display text drops the scheme, so a span has no `server.port` for a URL without an explicit port.

Userinfo is valid configuration: httpx2 sends it as `Authorization: Basic`, which is how a client gets through an authenticating reverse proxy. The fix keeps it in the request and out of every record.

## What Changes

- `LLMResponse` gets the field `origin: httpx2.Origin | None`. The Ollama, OpenAI-compatible and Claude paths set it with `httpx2.URL(url).origin` from the URL that they called. A reply that no endpoint sent, such as a cache hit, a pydantic-ai conversion or a test fake, has none.
- One label helper next to `LLMResponse`, `authority_label(host, port, scheme)`, writes `host[:port]` with the authority serialiser of httpx2. Every `"<type> (<host>)"` text uses it.
- `LLMClient` gets the origins of its configured URLs once. `backend_host` and `backend_info` are display text that the client writes from those origins. A configured URL that has no origin shows `unknown`.
- The ledger `server`, the counter `server` label and the span `server.address` and `server.port` come from the origin of the reply. A reply with no origin uses the configured origins. The ledger and the counters get the label of the client. The span gets the configured origin when there is exactly one.
- `server.port` is set each time `server.address` is set, with the default port of the scheme when the URL has none.
- A streamed Ollama call keeps the origin of the leased server, and an embedding request names its server from the origin of its endpoint.
- The served_by displays read the value with one parse next to the label helper. These displays are the table of `devops ai cost report --by backend` and the review benchmark. httpx2 reads an absolute URL, and `read_url_or_authority` reads a bare `host[:port]`. A value that neither reads shows `unknown`.
- The change deletes `_extract_server_from_backend_info`, `_server_span_attributes` and every `urlparse(...).netloc` read of an AI URL.
- The display text, the ledger and the counters see these changes, so the change has the spec delta `ai-reply-server`.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `ai-reply-server`: how devops-cli names the server of an AI request. The name shows in output, in the spend ledger, in metric labels, in spans and in the response cache.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/ai/client/models.py`, `unified.py`, `ollama.py`, `openai.py`, `claude.py`, `network.py`.
- `src/devops_cli/ai/rag/embeddings.py`.
- `src/devops_cli/commands/ai_cost.py`, `src/devops_cli/commands/review.py`, `src/devops_cli/config/constants.py`.
- `src/devops_cli/docs/generator.py` and the `docs/TELEMETRY.md` that it writes.
- `tests/ai/client/test_reply_server.py`, `tests/test_ai_client_telemetry.py`, `tests/test_telemetry.py`, `tests/test_ai_served_by.py`, `tests/test_review_profile.py`, `tests/test_rag_embeddings.py`.

## Feasibility

- The leak is real on `origin/main` at `4226904e`. An offline probe configured `ai.ollama_urls = ["http://user:pw@example.com:11434"]` and answered the call with an httpx2 `MockTransport`. The server got `Authorization: Basic dXNlcjpwdw==`. `client.backend_info` and the reply's `backend_info` were `ollama (user:pw@example.com:11434)`. The ledger row was `('user:pw@example.com:11434', 'ollama (user:pw@example.com:11434)')`, the counter `server` label was `user:pw@example.com:11434`, and the response-cache file held the text.
- The new failing tests show the same leak for the gateway URL, for a streamed call over two Ollama URLs and for an embedding request. `_backend_host("u:pw@example.com:11434")` of the review benchmark gave `u:pw@example.com:11434`, and the cost report showed `user:pw@example.com:11434`.
- httpx2 2.13.1 (the exact pin in `pyproject.toml`) lists `Origin` in `httpx2.__all__`. `httpx2.URL("http://user:pw@example.com:11434").origin` gave `Origin(scheme='http', host='example.com', port=11434)`, and `httpx2.URL("https://api.anthropic.com/v1").origin` gave port 443.
- `httpx2.URL(scheme=..., host=..., port=...).netloc` gave `example.com:11434`, `[2001:db8::1]:11434` and `api.anthropic.com`. It lowercases the host, writes an IDN host as its A-label and leaves out the default port of the scheme. With no scheme it keeps every port.
- `httpx2.URL(u).origin` raises `ValueError` for a URL with no scheme and `httpx2.InvalidURL` for `http://[::1`. `devops_cli.http.urls.get_url_origin` (from #1112) returns `None` for both.
- The settings refuse a URL without an httpx2 origin (`_validate_http_url` in `config/settings.py`). Thus only a config that skips validation can give the client such a URL.

## Existing Tool Considered

httpx2 is the HTTP client that sends every AI request, and it is a direct dependency. Its `URL.origin` gives the scheme, host and port that it sends to, and never the userinfo. Its `URL.netloc` writes an authority. The shared readers of #1112 in `devops_cli.http.urls` (`get_url_origin` and `read_url_or_authority`) read a URL or a bare `host[:port]`. The change builds no parser of its own. It deletes `_extract_server_from_backend_info` and `_server_span_attributes` in `ai/client/unified.py`, and the `urlparse(...).netloc` reads in `unified.py` and `ollama.py`. It also deletes the `urlsplit(endpoint).netloc` read in `ai/rag/embeddings.py`. It deletes the `urlparse` and `urlsplit` reads of served_by in `commands/ai_cost.py` and `commands/review.py` too.

# Design

## Decisions

- **The reply holds an `httpx2.Origin`.** `LLMResponse.origin` is `httpx2.URL(url).origin` of the URL that the provider called: `base` in the Ollama path, `self._api_base()` in the OpenAI-compatible path and the `base_url` of the Anthropic client in the Claude path. httpx2 sends the request, so its origin names the host and port that got the request. An origin has a scheme, a host and a port, and never userinfo. It is public in httpx2 2.13.1, hashable and comparable.
- **One label helper writes the text.** `authority_label(host, port, scheme="")` in `ai/client/models.py` returns `httpx2.URL(scheme=scheme, host=host, port=port).netloc.decode("ascii")`. It is the only `.netloc` read in the AI client. `origin_label(origin)` calls it with the scheme, host and port of an origin, so a reader of an origin does not repeat the three fields. With a scheme, the default port of that scheme is left out. With no scheme, as for a bare served_by authority, every port stays.
- **The text is `host[:port]` as httpx2 writes it.** For a URL without userinfo it is the same as the earlier `urlparse().netloc` text, with three exceptions. The host is lower case, an IDN host is its A-label, and an explicit default port (`:80` for http, `:443` for https) is left out. A config with such a URL starts new ledger `server` groups and new counter series. Price overrides are stored and found in lower case, so the lower-case host keeps its override. An override keyed on `:80`, `:443` or a Unicode host stops to match.
- **The IDN edge is accepted.** `_is_configured_ai_server_host` in `ai/spend/pricing.py` compares the server host with the Unicode host of the settings. The A-label of an IDN host does not match it, so pricing can treat an IDN-named configured server as remote. The pull request body names this edge.
- **The client gets its configured origins once.** `LLMClient._configured_origins` is a `functools.cached_property`. It holds `get_url_origin(u)` of each configured URL: every `ai.ollama_urls` entry for Ollama, `ai.gateway_url` for the gateway, and `ai.api_base_url` or the provider default for the others. `backend_host` joins the labels of the origins. An URL with no origin shows `unknown` (`CONST_AI_BACKEND_HOST_UNKNOWN`), never its own text.
- **A reply with no origin uses the configured origins.** The ledger `server` and the counter label are `backend_host`, as before. The span gets `server.address` and `server.port` from the one configured origin when there is exactly one. With several or none, the span names no server, as the stream span already does.
- **A stream keeps the origin of the leased server.** `network.stream_server` holds an `httpx2.Origin`. The stream span opens before the client leases a server, so it names a server only when exactly one is configured. The ledger names the leased server, as the `ai-spend-pricing` spec requires.
- **The embedding request names its server the same way.** It uses the same AI URLs and writes the same ledger and counters. Its ledger `server` and `backend_info` come from the origin of its endpoint, and its `ai.rag.ollama_embed_batch` span gets `server.address` and `server.port` from the origin. It uses `origin_span_attributes`, the span helper next to the label helper, as the chat client does. Without this, a password in `ai.ollama_urls` stays in the ledger through embeddings.
- **One parse for the served_by displays.** `served_by_authority(served_by)` sits next to the label helper. It reads an absolute URL with `get_url_origin` and a bare `host[:port]` with `read_url_or_authority`, the shared reader of #1112. It returns the host and the label, or `None` when neither reader gives a host and a valid port. The cost report shows the label, and the review benchmark shows the host with its in-cluster shortening. Both show `unknown` for `None`.
- **Configured userinfo stays valid.** httpx2 sends it as Basic authentication, which an Ollama behind an authenticating proxy needs. Whether the settings refuse userinfo belongs to #1000.
- **Rows already written stay as they are.** A rewrite of stored `backend_info` needs the parse-back that this change deletes. The pull request body tells a person who configured userinfo to change that password, and to run `devops ai cost reset` and `devops ai cache clear`.
- **#1001 adapters.** This change owns the field on `LLMResponse`. An adapter of #1001 sets it where it knows the base URL. Until then, its replies use the configured origins.
- **#606.** `_set_response_span_attributes` writes `server.address` and `server.port` only from an origin. The span event keeps `backend_info`, which is now the label text and holds no userinfo.

## Rejected alternatives

- **A `str` field.** Text invites the next parse-back, which is the cause of this defect.
- **A pydantic URL type.** For `http://example.com\@169.254.169.254/`, pydantic 2.13.5 gives host `example.com`, but httpx2 gives `Origin(scheme='http', host='169.254.169.254', port=80)`. The field must come from the parser of the client that sends.
- **The full origin as the text (`http://example.com:11434`).** It shows the scheme, but it splits the ledger history and changes the label of every counter series. The field already holds the scheme for a reader that needs it.
- **Mask the userinfo in the text with `mask_secrets`.** The masked text stays the data model, and the parse-back stays. The structured origin removes the cause.
- **Refuse userinfo in the settings.** It breaks working Basic authentication, and #1000 owns the validation of URL settings.
- **Rewrite the stored rows.** It needs the deleted parse-back, and the project keeps no backward compatibility before 1.0.0.

## Non-goals

- The `qdrant.upsert_points` span writes `str(self.base_url)` of the Qdrant URL as `server.address`. The Qdrant URL is not an AI URL, so #2459 changes it.
- `devops ai cost report` fails in `pricing.is_local` on a stored served_by such as `http://[::1`. `extract_served_by` refuses such a value now, so only old ledger rows hold one. #2462 asks for a guarded pricing read.

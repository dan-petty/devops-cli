# Proposal

## Why

Issue #2422 is part 1 of the split of #1381. The AI service clients in the table below build a raw `httpx2.Client`, call `httpx2.get`, or let pydantic-ai build its own client. Most of them check the host name with a pre-flight check (`validate_url_egress`, `validate_service_url`, `validate_configured_service_url`, `validate_url` or `is_cloud_metadata_host(..., resolve_dns=True)`). Then httpx2 resolves the name again at the socket. A rebinding DNS server can give a different address at the second lookup. #898 closed this window for the callers that it moved to the egress-checked factory (`devops_cli.http.client`). This change moves the AI service callers.

| Caller | Client before | Pre-flight check that goes | Level after |
| :--- | :--- | :--- | :--- |
| Gateway model info (`fetch_model_info`) | raw `httpx2.Client` | `validate_url_egress` | configured |
| Gateway health probe (`GatewayRouter.probe_gateway`) | raw `httpx2.Client` | `validate_url_egress` | configured |
| Backend probe (`GatewayRouter.probe_backend`) | raw `httpx2.Client` | `validate_url_egress` | configured |
| `devops ai gateway connect` probe | raw `httpx2.Client` | `validate_url_egress` | private |
| `devops ai gateway load` Prometheus query (`prometheus_query`) | raw `httpx2.Client` | `validate_url_egress`, `validate_service_url` | the level of the caller: configured |
| Embeddings engine: the batch client, the Ollama batch, the two dimension probes | raw `httpx2.Client` (4) | `validate_configured_service_url` (4) | configured |
| `devops ai cost update-pricing --source <url>` | `httpx2.get` | none | configured |
| Default pricing registry | `httpx2.get`, and the dead `UpdatePrices.fetch` branch | none | public |
| Documentation crawler (`DocsIngester.ingest_remote_docs`) | raw `httpx2.Client` | `validate_service_url` (2) | public |
| pydantic-ai Ollama model (`create_ollama_provider`) | the own client of pydantic-ai | `is_cloud_metadata_host(..., resolve_dns=True)`, `validate_url` | configured |
| Benchmark endpoints | the AI client and the embeddings engine | `validate_service_url` (`--servers`), `validate_url` (2) | configured |
| pydantic-ai provider base URL (`create_pydantic_ai_provider`) | factory client, configured | `validate_configured_service_url` | configured |

"Configured" is loopback and public addresses, and private addresses too when `ai.allow_private_network` is true (`configured_level`). Cloud metadata addresses are refused at every level.

## What Changes

- Each caller in the table gets its client from `new_http_client` or `new_async_http_client` at its level. The client resolves the host once, at the connect, and dials only the addresses that its level admits. The factory checks each redirect hop the same way.
- The pre-flight address checks in the table are deleted. The `allow_private` parameters of `normalize_ollama_base_url` and `create_ollama_provider` are deleted. `create_ollama_provider` and `create_ollama_model` take the `AIConfig` whose flag sets the level.
- Checks that read only the URL stay where a command needs an early error: `normalize_ollama_base_url` still refuses a scheme other than http and https, and `devops ai benchmark --servers` checks each URL with the type of `ai.ollama_urls` (`HttpUrlStr`) before the run.
- `prometheus_query` takes the egress level from its caller. `devops ai gateway load` gives the configured level.
- The bridge no longer turns an address refusal into a `ConfigurationError` when it builds a remote model, because no check runs at that time. A request to an address that the level refuses raises `SSRFBlockedError` at the connect.
- Some levels change. The Ollama model of pydantic-ai is narrower: a private Ollama needs `ai.allow_private_network` on this path too. The `--source` URL of the pricing update is narrower: a private source needs the flag. The default pricing registry and the documentation crawler dial only public addresses, whatever the flag says. The gateway and backend probes, the pool-load query and the benchmark endpoints are wider: a loopback answer is dialled without the flag. A name that answers loopback reaches the embeddings and the provider base URL without the flag.
- `README.md`, `docs/KNOWN_ISSUES.md` and the pydantic-ai page of the knowledge base name the moved clients. The general statement that every HTTP client is checked at the connect waits for part 5 (#2437).
- A consumer sees the levels and the refusals, so the change carries a spec delta. It adds four requirements to the capability `configured-service-urls`.
- This change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `configured-service-urls`: four new requirements. "Configured AI service clients dial at the configured level" gives the level of the clients whose URL comes from the configuration. "The gateway connect probe dials private addresses" gives the level of the `devops ai gateway connect` probe. "The pricing registry and the documentation crawler dial only public addresses" gives the public level of these two clients. "AI service clients dial the address that they checked" says that each of these clients resolves the host one time, at the connect, and gives the socket the address that it checked.

## Impact

- `src/devops_cli/ai/gateway.py`, `src/devops_cli/commands/ai_gateway.py`, `src/devops_cli/ai/pool_load.py`, `src/devops_cli/ai/rag/embeddings.py`, `src/devops_cli/ai/spend/pricing.py`, `src/devops_cli/ai/library/docs_ingester.py`, `src/devops_cli/ai/models/ollama.py`, `src/devops_cli/ai/pydantic_ai_bridge.py`, `src/devops_cli/ai/benchmark/runner.py`, `src/devops_cli/ai/benchmark/embedding_runner.py`, `src/devops_cli/commands/benchmark.py`, `src/devops_cli/ai/providers/__init__.py`.
- `tests/test_http_egress.py`, and the tests that faked the deleted checks or the raw clients.
- `README.md`, `docs/KNOWN_ISSUES.md`, `src/devops_cli/ai/knowledge_base/it_domains/tools/pydantic_ai.md`.

## Feasibility

- On `origin/main` at `acace034`, `rg -n -g '*.py' 'httpx2\.((Async)?Client|get|post|put|patch|delete|head|request|stream)\('` over the six files of the issue printed 12 raw clients: `ai/gateway.py:295`, `:488`, `:679`, `ai/pool_load.py:47`, `ai/rag/embeddings.py:460`, `:690`, `:784`, `:921`, `ai/spend/pricing.py:672`, `:684`, `ai/library/docs_ingester.py:257` and `commands/ai_gateway.py:167`. The `rg` for the pre-flight checks printed 19 lines in the files of the table.
- A raw client dials the host name. `ConnectRecorder` in `tests/web_fakes.py` stands in for `httpcore2.SyncBackend.connect_tcp` and `AnyIOBackend.connect_tcp`. With the new rows of `test_each_caller_dials_at_its_level` and `test_each_ai_service_caller_dials_the_address_it_checked` on the code before the move, the recorder got `example.com` from each raw client, so the socket resolves the name again after the check. A factory client gives the backend the vetted IP literal only.
- pydantic-ai 2.54.0 builds its own client when a provider gets no `http_client`: `OpenAICompatibleProvider._get_http_client` calls `create_async_httpx2_client()` (`pydantic_ai/providers/_openai_compatible.py`). `OllamaProvider.__init__` takes `http_client` and gives it to `AsyncOpenAI`.
- openai 3.26.1 retries and wraps only `request_exceptions()`: `httpx2.RequestError`, `ssl.SSLError` and `anyio.EndOfStream` (`openai/_httpx2.py`). `SSRFBlockedError` is none of them, so a refusal at the connect comes out of the model request at once and is not retried.
- genai-prices 0.1.9 gives `UpdatePrices.url` the default `DEFAULT_UPDATE_URL`, a dataclass field (`genai_prices/update_prices.py`). So `getattr(updater, "url", None)` is never empty, and the branch that calls `UpdatePrices.fetch()` with its own `httpx2.get` never runs.
- The factory owns the timeouts: `new_http_client(timeout=httpx2.Timeout(t))` gives each phase the bound `t`, as `httpx2.Client(timeout=t)` did. Its default limits (100 connections, 20 kept alive) are the httpx2 defaults.

## Existing Tool Considered

The change uses the egress-checked factory of #898 (`devops_cli.http.client`), which builds on the httpcore2 network backend API, and the `http_client` parameter that pydantic-ai providers take. The early URL check of `--servers` uses the `HttpUrlStr` type of the settings, which is pydantic `AnyHttpUrl` with an httpx2 origin check. The change builds no new check. It deletes these internal paths: the pre-flight calls in the table, `_is_cloud_metadata_host` in `ai/models/ollama.py`, the `allow_private` parameters of `normalize_ollama_base_url` and `create_ollama_provider`, the `UpdatePrices.fetch()` branch of the pricing fetch, and the `ConfigurationError` branch for an address refusal in `_resolve_remote_inferred_model`.

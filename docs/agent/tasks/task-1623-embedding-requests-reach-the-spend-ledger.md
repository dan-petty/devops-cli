# Task: Embedding Requests Reach the Spend Ledger and the AI Usage Counters (#1623)

**Issue**: [#1623](https://github.com/dan-petty/devops-cli/issues/1623)
**Scope**: scope/ai, scope/telemetry
**Feasibility**: Checked on 2026-10-23 at `origin/main` 4b06d316, read-only. In live Prometheus, the gateway served 477 `bge-m3:latest` `/v1/embeddings` requests in 24 h, and over 7 d `devops_cli_ai_requests_total` held one model, a chat model. `EmbeddingsEngine` (`src/devops_cli/ai/rag/embeddings.py`) did not call `track_request_spend`, which is the only writer of the ledger and the AI counters. The Ollama API document shows `prompt_eval_count` in an `/api/embed` reply. An OpenAI-compatible `/embeddings` reply carries `usage.prompt_tokens`, and the pydantic-ai 2.54.0 source says that some compatible servers omit it. genai-prices 0.1.9, with its bundled snapshot, prices `text-embedding-3-small` at $0.02 per million input tokens only when it gets `provider_id="openai"`. Without a provider it raises `LookupError`, because no provider pattern matches the name. Thus the provider of the reference models is a setting. `opentelemetry-semantic-conventions` 0.66b1 is in `uv.lock` as a dependency of the OpenTelemetry SDK, and its `GenAiOperationNameValues` holds `chat` and `embeddings`.

## Description
Each embedding request devops-cli sent was invisible: no ledger row, no request or token point, and no savings. The gateway's embedding traffic is most of its requests and most of its input tokens. Now the engine records each request that a provider answers, where the engine sends it. The tokens are those the reply counted. Local savings of embedding tokens use an embedding reference model, so they are not priced at the chat reference.

## Key Changes
- **Engine** (`ai/rag/embeddings.py`). `_record_embedding_request` calls `track_request_spend` with `request_type="embedding"` and 0 completion tokens. It names the configured provider and the netloc of the endpoint as the server, as a chat call does, so `is_local` decides the same way for both. The gateway's `x-litellm-model-api-base` header, when present, gives `served_by`. The engine records after `_reply_vectors` accepts the reply: in `_embed_single_openai_batch` after the retry loop, in `_query_ollama_node_batch`, and in both dimension probes. A batch that the gateway refuses with HTTP 429 and then answers is one row. `_post_openai_batch_with_retry` returns the time of the last attempt, so the row has no back-off time. Texts that the cache answers send no request and add no row.
- **Tokens**. The OpenAI-compatible reply gives `usage.prompt_tokens`, and the Ollama reply gives `prompt_eval_count`. A reply without a count gets the local `count_tokens` count of its texts, as a chat reply without usage does.
- **pydantic-ai embedding models**. `OllamaEmbeddingModel` and `EngineEmbeddingModel` (`ai/agents/embeddings.py`) report the input tokens of the requests they sent, through `embed_counting_tokens`. The estimate of words × 1.3 is gone. `embed_counting_tokens` observes the recorded calls with `observe_llm_calls`, so the worker threads of the engine also reach it.
- **Operation label** (`ai/spend/ledger.py`). The AI counters carry `operation`, the GenAI `gen_ai.operation.name` value from `GenAiOperationNameValues`: `embeddings` for an embedding row and `chat` for every other row. `pyproject.toml` declares `opentelemetry-semantic-conventions==0.66b1`.
- **Reference models**. `ai.reference_embedding_model` (default `text-embedding-3-small`) prices embedding tokens, and `ai.reference_provider` (default `openai`) is the genai-prices provider of both reference models. Both are in `config/defaults.py`, `config/settings.py`, `config/options.py`, `devops config show` and `config.example.yaml`. `_emit_local_cost_equivalent` and the report-time savings use the embedding reference for embedding tokens. The report queries count the embedding tokens of each server, model and stage with named SQL parameters. `LifetimeSpendReport` carries `reference_embedding_model`, `total_embedding_tokens` and `local_embedding_tokens`. `devops ai cost` names both reference models.
- **Review profile** (`ai/review/profile.py`). `ReviewProfiler.observe` counts an embedding request in `embedding_calls` and `embedding_tokens` of its stage and of the profile, not in `llm_calls` or the chat token totals. Its cost is part of the stage cost.
- **Dashboard** (`k8s/monitoring/dashboards/ai-spend.json`). "Token Processing Rate" groups by `operation` and `type`, and "Request Rate by Model" groups by `operation`, `model` and `provider`. "Response Cache Hit Share" divides by the requests whose `operation` is not `embeddings`, because the response cache answers no embedding request. The series sent before this change have no `operation` label, so they stay in the share.
- **Docs**. `docs/CONFIGURATION.md` and `docs/TELEMETRY.md` are generated again from the settings and the instrument descriptions.

## Decisions
- The engine records no row for a call that the cache answers. The issue allowed at most one cached row. With no row, the requests counter counts the HTTP requests sent, and the response-cache hit share keeps its meaning.
- The Ollama dimension probe is recorded too. It sends an `/api/embed` request like the OpenAI probe.
- The reference provider is a new setting, not a constant, because a person can set a reference model that another provider prices. A chat reference that the reference provider does not list resolves by its name, as before.
- The models in `ai/spend/models.py` take their reference defaults from `config/defaults.py`, not from a `"gpt-4o-mini"` literal, because the new field sits next to them.

## Acceptance Criteria
- [x] One gateway batch writes one row with `request_type="embedding"`, the reply's `usage.prompt_tokens`, 0 completion tokens and `served_by` from the gateway header: `test_a_gateway_batch_records_one_embedding_row_with_the_replys_tokens_and_backend`.
- [x] A batch retried after HTTP 429 writes one row, and parallel batches write one row each: `test_a_batch_retried_after_http_429_records_one_row`, `test_batches_sent_in_parallel_record_one_row_each`.
- [x] An Ollama `/api/embed` batch takes its tokens from `prompt_eval_count`: `test_an_ollama_batch_records_the_tokens_its_reply_counted`.
- [x] A call that the cache answers writes no row: `test_a_call_the_cache_answers_records_no_request`.
- [x] Each dimension probe writes one row: `test_the_dimension_probe_records_its_request[gateway|ollama]`.
- [x] Both pydantic-ai embedding models report the reply's token count: `test_the_embedding_models_report_the_tokens_the_provider_counted[ollama|engine]`.
- [x] An embedding row sends a request point and token points with `operation="embeddings"`, and a chat call sends `operation="chat"`: `test_ai_calls_count_requests_and_tokens_by_operation`.
- [x] Local savings of an embedding row use the embedding reference price, when the row is sent and in the report's total, servers, models and stages: `test_local_embedding_savings_are_priced_at_the_embedding_reference`, `test_local_savings_price_embedding_tokens_at_the_embedding_reference`, `test_the_embedding_reference_is_a_setting`.
- [x] A review profile keeps embedding requests out of `llm_calls` and the chat token totals and reports them apart: `test_embedding_requests_are_counted_apart_from_llm_calls`.
- [x] The dashboard charts AI requests and tokens by `operation`, and the hit share leaves out embedding requests: `test_the_dashboards_chart_latency_errors_reviews_and_findings_devops_cli_sends`, `test_the_hit_share_panel_divides_cached_requests_by_all_requests_over_an_hour`.
- [x] `devops config show` lists both reference models and the reference provider: `test_config_show_includes_the_reference_models_and_their_provider`.
- Pending a person: after a day of normal use, compare `sum(increase(devops_cli_ai_requests_total{operation="embeddings"}[24h]))` with the gateway's `/v1/embeddings` count for the same day. The two must agree within a few percent. Hourly agreement waits for #1132.

## Not in this item
- A spend point of 0 for each local request, `served_by` in `is_local` and in the cost, local overrides, and the ledger exposition names: #1631.
- One reference price per request kind for every process, and a warning for an unknown model or reference: #1672.
- One `server` value for each configured gateway: #1110.
- Rows for the attempts that the gateway failed: #1019.

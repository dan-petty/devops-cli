# Proposal

## Why

Issue #2031: the spend ledger priced a hosted gateway call at the route name that the client asked for, for example `devops-chat`. genai-prices does not know a route name, so the call cost $0 with the pricing source `unknown`. The LiteLLM gateway names the deployment model that served the call in the `x-litellm-model-name` reply header, for example `openai/gpt-4o`. devops-cli did not read this header.

## What Changes

- devops-cli reads the `x-litellm-model-name` header of a gateway reply for a blocking chat call, a streamed chat call and an embedding request. `CONST_AI_GATEWAY_SERVED_MODEL_HEADER` in `src/devops_cli/config/constants.py` holds the header name, and `extract_served_model` in `src/devops_cli/ai/client/network.py` reads it. Only these two files name a gateway reply header. `tests/test_url_credential_masking.py` now checks this rule for both headers.
- `PricingRegistry.calculate_request_cost` takes `served_model`. When the reply names a deployment model, a hosted call is priced at that model, as a LiteLLM model reference: genai-prices gets the provider ID `litellm` and takes the provider from the prefix. A price override of the deployment model applies, and a price override of the route name does not. When the reply names no deployment model, the call is priced at the model that the client asked for, as before. A local call stays local.
- The model that the client asked for stays the `model` of the spend-ledger row and the `model` label of `devops_cli_ai_requests_total`, `devops_cli_ai_tokens_total` and `devops_cli_ai_spend_usd_total`. Thus the dashboards and `devops ai cost` still group by the route name.
- Each spend-ledger row stores the deployment model in the new column `served_model`. An existing ledger gets the column and keeps its rows.
- The description of `devops_cli_ai_spend_usd_total` in `docs/TELEMETRY.md` and the help of `devops ai cost set-price` say which model prices a gateway call.
- The value of a metric, the spend ledger and the help of a command change, so the change has a spec delta. It adds requirements to `ai-spend-pricing`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-spend-pricing`: adds the requirements that a hosted gateway call is priced at the deployment model that the gateway names, that the route name stays the model of the row and of the metrics, and that each row stores the deployment model.

## Impact

- Code: `src/devops_cli/config/constants.py`, `src/devops_cli/ai/client/network.py`, `models.py`, `openai.py` and `unified.py`, `src/devops_cli/ai/rag/embeddings.py`, `src/devops_cli/ai/spend/pricing.py`, `ledger.py` and `models.py`, `src/devops_cli/telemetry/instruments.py` and `src/devops_cli/commands/ai_cost.py`.
- Documents: `docs/TELEMETRY.md`, `docs/CLI_REFERENCE.md` and `docs/commands/ai.md`, generated again.
- Tests: `tests/test_ai_served_by.py`, `tests/test_ai_spend_pricing.py`, `tests/test_ai_spend_ledger.py`, `tests/test_rag_embeddings.py`, `tests/test_telemetry_instruments.py` and `tests/test_url_credential_masking.py`.
- Today each route in `k8s/llm/gateway/config.yaml` sends its calls to an Ollama deployment in the cluster, so each live gateway call is local. The live spend changes only when a hosted deployment serves a call.

## Feasibility

- LiteLLM 1.103.0 source, read in the gateway pod (image `ghcr.io/berriai/litellm:v1.103.0`, read-only `kubectl -n llm exec deploy/llm-gateway -- python -c ...`): `ProxyBaseLLMRequestProcessing.get_custom_headers` sets `x-litellm-model-name` to `_get_deployment_model_name(litellm_logging_obj)`. That function reads `deployment` from the `litellm_metadata` or `metadata` of the `litellm_params` of the call. Its docstring says that the router writes the model-group alias that the client asked for in the `model` field of the reply. Thus the reply body and the other headers do not name the deployment model.
- `Router._update_kwargs_with_deployment` sets `deployment` to `litellm_params.model` of the deployment that it selects, and `api_base` from the same deployment. Thus `x-litellm-model-name` and `x-litellm-model-api-base` name the same deployment.
- Each call of `get_custom_headers` in `litellm/proxy/common_request_processing.py` gives the logging object: the blocking reply, the streamed reply and the failure reply. `/v1/embeddings` goes through `base_process_llm_request`, as `/v1/chat/completions` does.
- Live Prometheus, read-only through Grafana on 2026-10-24: in the last 7 days, `devops_cli_ai_requests_total{provider="gateway"}` had three `backend` values, one for each Ollama tier that served a call. devops-cli takes these values from `x-litellm-model-api-base`, which the same `get_custom_headers` call sets. The `model` values were the models that the clients asked for.
- genai-prices 0.1.9, installed source: `DataSnapshot.find_provider_model` takes the provider ID `litellm` with a model reference that has a `/`. It takes the provider ID from the prefix and the model from the remaining text, when `find_provider_by_id` knows the provider. `find_provider_by_id` also uses the `provider_match` of each provider, so `bedrock` finds `aws`.
- An offline probe of the bundled snapshot with the provider ID `litellm` and 1,000,000 input tokens gave these prices and providers: `openai/gpt-4o` $2.50 (openai), `openai/text-embedding-3-small` $0.02 (openai), `bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0` $3.00 (aws), `openrouter/anthropic/claude-3.5-sonnet` $3.00 (openrouter), `gemini/gemini-2.5-flash` and `vertex_ai/gemini-2.5-flash` $0.30 (google), `azure/gpt-4o` $2.50 (azure), and `anthropic/claude-sonnet-4-5` (anthropic). `ollama_chat/qwen3.8:27b` and `devops-chat` gave `LookupError`. With no provider, `text-embedding-3-small` and `openai/gpt-4o` gave `LookupError`. With the provider `gateway`, each model gave `LookupError`.
- On the base commit, the ten new tests failed: the ledger had no `served_model` column, `track_request_spend`, `SpendLedger.record_request` and `PricingRegistry.calculate_request_cost` took no `served_model`, and no source file named `x-litellm-model-name`.

## Existing Tool Considered

- genai-prices, the price source of the ledger, reads a LiteLLM model reference itself under the provider ID `litellm`. devops-cli gives it the deployment model with this provider ID. devops-cli holds no table of LiteLLM prefixes and does not split the reference.
- LiteLLM sends its own cost of a call in `x-litellm-response-cost`. Rejected: the ledger keeps one price source for each call: genai-prices, with its snapshot update and the price overrides of `devops ai cost set-price`. A call to a provider without the gateway has no such header.
- `litellm.get_llm_provider` also splits a LiteLLM model reference. Rejected: litellm is not a dependency of devops-cli, and genai-prices already does the split.
- The change deletes no code. `_parse_compat_response` takes the reply headers in place of the backend, and reads the backend and the deployment model from them.

# Design

## Context

`track_request_spend` in `src/devops_cli/ai/spend/ledger.py` prices each call with `PricingRegistry.calculate_request_cost`, at the model that the client asked for. For a gateway call, this model is the route name, such as `devops-chat`. A reply of the LiteLLM gateway names the backend in `x-litellm-model-api-base`, which decides if the call is local or hosted (#1631). It names the deployment model in `x-litellm-model-name`. See proposal.md for the evidence.

## Goals / Non-Goals

**Goals:**

- A hosted gateway call is priced at the deployment model that served it, for a blocking chat call, a streamed chat call and an embedding request.
- The spend ledger, the metrics and `devops ai cost` keep the model that the client asked for.

**Non-Goals:**

- A metric label for the deployment model. The ledger holds it.
- The `gen_ai.response.model` attribute of the inference span. It keeps the model of the reply body.
- A change to the reference prices that price the local tokens on the dashboard (#1672). See the record below.

## Decisions

- **genai-prices reads the deployment model as a LiteLLM model reference.** The registry gives genai-prices the provider ID `litellm` (`CONST_GENAI_PRICES_LITELLM_PROVIDER`), and genai-prices takes the provider from the prefix. Rejected: price the deployment model under the request provider, `gateway`, and then with no provider, as the registry does for other models. genai-prices knows no provider `gateway`. With no provider, it gave `LookupError` for `text-embedding-3-small`, because no provider has a `model_match` for this model. Rejected: a table from LiteLLM prefixes to genai-prices providers. genai-prices already holds this map in `provider_match`.
- **The deployment model is the target of a price override.** When the reply names a deployment model, the override of that model applies, and the override of the route name does not. A route can send calls to a local deployment and to a hosted deployment, and the price belongs to the deployment. The help of `devops ai cost set-price` says this. Rejected: the override of the route name first. It gives one price to each hosted deployment of the route.
- **The local check comes first.** The backend that served the call decides if it is local before the registry reads the deployment model. Thus a local deployment, such as `ollama_chat/qwen3.8:27b`, stays local and costs nothing.
- **The route name stays the model of the row and of the metrics.** The issue asks for this, and the dashboards and `devops ai cost --by model` group by it. Rejected: write the deployment model in `model`. A route then has one series for each deployment, and the request counts do not show what the clients asked for.
- **The ledger stores the deployment model in `served_model`.** A row that `genai_prices:openai` priced then shows the model that set its price. Rejected: no column. The row then shows only `devops-chat` and `genai_prices:openai`, and a person cannot see which model priced it.
- **No metric label for the deployment model.** No dashboard reads it, and each deployment adds series. The ledger holds it.
- **Only `config/constants.py` and `ai/client/network.py` name a gateway reply header.** `extract_served_model` reads the header in `network.py`, next to `extract_served_by`. A streamed reply keeps the deployment model in the context variable `stream_served_model`, as it keeps the backend. `tests/test_url_credential_masking.py` checks the rule for the two headers.

## Record: the reference models of the dashboard

On 2026-10-24 the owner confirmed that the AI spend dashboard prices local tokens at the default reference models: `gpt-4o-mini` for chat and `text-embedding-3-small` for embeddings. This answers the "Pending a person" bullet about the reference models in `openspec/changes/archive/2026-10-24-1672-local-savings-reference-prices/tasks.md`.

## Risks / Trade-offs

- [A gateway does not send `x-litellm-model-name`] → The call is priced at the route name, as before. Its source is `unknown`, and the registry logs one warning that names the route name.
- [genai-prices does not know a deployment model] → The call costs $0 with the source `unknown`, and the registry logs one warning that names the deployment model and the provider `litellm`.
- [Rows from before the change have no `served_model`] → Their recorded cost does not change.

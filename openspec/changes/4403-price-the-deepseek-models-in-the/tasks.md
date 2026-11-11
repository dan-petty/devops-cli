# Tasks

## 1. Price each hosted group and its cached input

Kind: behavior. Reads: `src/devops_cli/ai/spend/pricing.py`, `src/devops_cli/ai/spend/ledger.py`, `src/devops_cli/roadmap/agent_run.py`, `k8s/llm/gateway/config.yaml`, `k8s/devops/configmap.example.yaml`. Changes: `tests/ai/spend/test_hosted_group_prices.py` (new), `tests/ai/client/test_roadmap_agent_run.py`, `tests/ai/spend/test_ai_spend_pricing.py`, `src/devops_cli/ai/spend/models.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/ai/spend/pricing.py`, `src/devops_cli/ai/spend/ledger.py`, `src/devops_cli/roadmap/agent_run.py`.

- [x] 1.1 Add `tests/ai/spend/test_hosted_group_prices.py` and the DeepSeek run and counter test in `tests/ai/client/test_roadmap_agent_run.py`. Move the tests that used DeepSeek as the unpriced example to a model that nothing prices. Run them and see them fail
  - Verification: `$ uv run devops ci test tests/ai/spend/test_hosted_group_prices.py tests/ai/client/test_roadmap_agent_run.py` fails on the base
- [x] 1.2 Add the cached input rate to `ModelPricing` and `AIPriceOverride`, `_HOSTED_GROUP_PRICES` to the registry, and `cache_read_tokens` to `calculate_request_cost`, `track_request_spend` and `record_run_spend`
  - Verification: `$ uv run devops ci test tests/ai/spend/test_hosted_group_prices.py tests/ai/client/test_roadmap_agent_run.py tests/ai/spend/test_ai_spend_pricing.py tests/ai/spend/test_pricing_registry_overrides.py` passes

## 2. The gateway holds the same price

Kind: other. Reads: `k8s/llm/gateway/config.yaml`. Changes: `k8s/llm/gateway/config.yaml`.

- [x] 2.1 Set the input, cached input and output prices of the group `deepseek-v4.1-flash-1017` to 0.0784, 0.0024 and 0.2352 USD per million tokens, with the source and the date in the comment
  - Verification: `$ uv run devops ci test tests/ai/spend/test_hosted_group_prices.py tests/ai/benchmark/test_k8s_llm_gateway.py` passes

## 3. Documents

Kind: other. Reads: `docs/TELEMETRY.md`, `k8s/README.md`. Changes: `src/devops_cli/telemetry/instruments.py`, `docs/TELEMETRY.md`, `k8s/README.md`.

- [x] 3.1 State in the description of `devops_cli_ai_spend_usd_total` that a cached prompt token costs the cached input rate, and regenerate the documents. State in `k8s/README.md` how devops-cli prices each hosted group
  - Verification: `$ uv run devops docs generate --sync-readme` leaves no further diff

## Workflow follow-up

- A chat call of `LLMClient` reads no cached prompt tokens from its reply, so it keeps the prompt price for each prompt token (#4442).
- Pending a person: compare the rates with the account activity of OpenRouter for one day of gateway calls (#4422).
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

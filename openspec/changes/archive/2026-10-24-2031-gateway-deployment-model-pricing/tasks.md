# Tasks

## 1. Price a hosted gateway call at its deployment model

- [x] 1.1 Write `test_a_hosted_gateway_reply_is_priced_at_the_deployment_model_that_it_names` in `tests/test_ai_served_by.py`, `test_a_gateway_call_is_priced_at_the_litellm_reference_of_its_deployment_model` and `test_a_price_override_of_the_deployment_model_prices_a_gateway_call` in `tests/test_ai_spend_pricing.py`, `test_a_hosted_gateway_embedding_is_priced_at_the_deployment_model_that_it_names` in `tests/test_rag_embeddings.py` and `test_a_call_priced_at_its_deployment_model_keeps_the_route_name_as_its_model_label` in `tests/test_telemetry_instruments.py`, extend the gateway header rule of `test_no_forbidden_constructs_remain` in `tests/test_url_credential_masking.py` to `x-litellm-model-name`, and verify that they fail on the base (`uv run devops ci test tests/test_ai_served_by.py tests/test_ai_spend_pricing.py tests/test_rag_embeddings.py tests/test_telemetry_instruments.py tests/test_url_credential_masking.py`)
- [x] 1.2 Add `CONST_AI_GATEWAY_SERVED_MODEL_HEADER`, `extract_served_model` and `stream_served_model`, carry `served_model` on `LLMResponse` and from the blocking, streamed and embedding paths to `track_request_spend`, and price it in `PricingRegistry.calculate_request_cost` under `CONST_GENAI_PRICES_LITELLM_PROVIDER` (`uv run devops ci test tests/test_ai_served_by.py tests/test_ai_spend_pricing.py tests/test_rag_embeddings.py tests/test_telemetry_instruments.py tests/test_url_credential_masking.py tests/test_ai_client_telemetry.py tests/test_ai_streaming.py tests/test_response_cache.py`)
- [x] 1.3 Describe the price of a gateway call in the description of `devops_cli_ai_spend_usd_total` and in the help of `devops ai cost set-price`, and generate the documents again (`uv run devops docs generate --sync-readme`, then `uv run devops docs check`)

## 2. Record the deployment model in the spend ledger

- [x] 2.1 Write `test_an_existing_ledger_gains_the_served_model_column` in `tests/test_ai_spend_ledger.py`, and verify that it fails on the base (`uv run devops ci test tests/test_ai_spend_ledger.py`)
- [x] 2.2 Add the `served_model` column, its in-place addition to an existing ledger and the `served_model` field of `SpendRecord`, and store the deployment model in `track_request_spend` (`uv run devops ci test tests/test_ai_spend_ledger.py tests/test_ai_served_by.py tests/test_ai_spend_cli.py tests/test_ai_spend_prometheus.py`)

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

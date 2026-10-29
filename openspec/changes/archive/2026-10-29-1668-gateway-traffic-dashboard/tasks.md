# Tasks

## 1. A call to the gateway names devops-cli and its service

- [x] Add failing tests: a chat call, an embedding call and a pydantic-ai agent call to the gateway name `devops-cli/<release>` and the service name; a chat call to another provider names no end user; the broker's User-Agent is the installed release
  - Verification: `uv run devops ci test tests/ai/client/test_gateway_caller_headers.py`
- [x] Add `otel_service_name()`, `user_agent()`, `gateway_caller_headers()` and the `name_gateway_caller` hook, and set the headers on the OpenAI client, the embeddings client and the pydantic-ai gateway client; the broker uses `user_agent()`
  - Verification: `uv run devops ci test tests/ai/client/test_gateway_caller_headers.py tests/test_ai_chat_reply_stream.py tests/test_rag_embeddings.py tests/test_pydantic_ai_profiles_and_providers.py`

## 2. The gateway writes the caller, and Open WebUI calls only the gateway

- [x] Add a failing test that the gateway config sets `enable_end_user_cost_tracking_prometheus_only`, and change the Open WebUI test to expect no `ollamaUrls`
  - Verification: `uv run devops ci test tests/test_k8s_llm_gateway.py`
- [x] Set the gateway setting, drop `ollamaUrls`, and update `k8s/README.md` and `k8s/llm/profiles/README.md`
  - Verification: `uv run devops ci test tests/test_k8s_llm_gateway.py` and `uv run devops docs check`

## 3. The AI spend dashboard counts every caller

- [x] Add failing tests: the request and token stats take gateway traffic from the gateway's series; the gateway row holds attempts by status, traffic by caller and coverage; each gateway series of the dashboard is in the LiteLLM capture and read as a counter
  - Verification: `uv run devops ci test tests/test_k8s_monitoring_dashboards.py tests/test_stack_dashboards.py tests/test_telemetry_instruments.py`
- [x] Change the two stats, add the row and its three panels, fix the legends of Ollama Slot Wait by Priority (p95), and scope the delta-series limits to panels that read a devops-cli series
  - Verification: `uv run devops ci test tests/test_k8s_monitoring_dashboards.py tests/test_stack_dashboards.py tests/test_telemetry_instruments.py tests/test_grafana_dashboards.py`
- [x] Describe the gateway counts in `k8s/README.md`, and regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 4. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 1668-gateway-traffic-dashboard`
- Pending a person: under Open WebUI's Admin Panel > Settings > Connections, turn off the Ollama API. Open WebUI keeps the setting in its database, so the new values change only a fresh install.
- Pending a person: after Argo CD redeploys the gateway and a workstation runs a model call, `sum by (end_user) (increase(litellm_input_tokens_metric_total[1h]))` shows `devops-cli`, and the Gateway Traffic from Every Caller row shows data in Grafana.
- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).

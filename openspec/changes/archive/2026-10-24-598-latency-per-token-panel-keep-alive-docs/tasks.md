# Tasks

## 1. Latency per output token on the LLM stack dashboard

- [x] 1.1 Write `test_llm_stack_dashboard_shows_latency_per_output_token_beside_time_to_first_token` in `tests/test_stack_dashboards.py`, and verify that `uv run devops ci test tests/test_stack_dashboards.py` fails on the base in this test
- [x] 1.2 Read in the gateway pod how LiteLLM 1.103.0 computes `litellm_deployment_latency_per_output_token`, run the two queries with the Grafana MCP `query_prometheus`, add the panel to `k8s/monitoring/dashboards/llm-stack.json` with a description of what the metric measures, and verify that `uv run devops ci test tests/test_stack_dashboards.py tests/test_grafana_dashboards.py tests/test_k8s_monitoring_dashboards.py tests/test_llm_pool_metrics.py` passes
- [x] 1.3 Write the `llm-stack-dashboard` delta with the requirement and the scenario that the test of 1.1 checks, and verify that `uv run devops openspec check` passes

## 2. Ollama keep-alive, loaded models and slot lease in the texts

- [x] 2.1 Add the `ollama ps` command for one tier and the keep-alive behaviour to `src/devops_cli/ai/knowledge_base/it_domains/tools/ollama.md`, set its `applies_to` to `tool:ollama@0.34.*`, and verify that `uv run devops ci test tests/test_kb.py tests/test_kb_manuals_metadata.py` passes
- [x] 2.2 Say in the docstring of `acquire_ollama_slot` that the lease counts in this process only, and why, and verify that `uv run ruff check src/devops_cli/ai/client/network.py`, `uv run mypy src/devops_cli/ai/client/network.py` and `uv run devops ci test tests/test_ai_request_priority.py` pass
- [x] 2.3 Run `uv run devops docs generate --sync-readme`, and verify that `uv run devops docs check` and `uv run devops openspec check` pass

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

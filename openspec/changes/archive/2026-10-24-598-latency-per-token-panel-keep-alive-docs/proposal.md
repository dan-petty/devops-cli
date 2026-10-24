# Proposal

## Why

Issue #598 asked for seven parts on Ollama model residency: a time-per-output-token histogram, p50 and p95 of that histogram in `devops ai cost report --by backend`, a decision on `record_llm_metrics`, `/api/ps` for each pod in `devops ai gateway status`, keep-alive on the chat bodies and `OLLAMA_KEEP_ALIVE` on each tier, models that fit each pod, and a statement that `acquire_ollama_slot` counts per process by design. A check of each part against the live cluster and the upstream source on 2026-10-24 found that open tools already cover two parts, that two parts are done, and that the keep-alive premise is false. The LLM stack dashboard shows no latency per output token, and the Ollama manual and the `acquire_ollama_slot` docstring do not record the behaviour that the check found. This change delivers that remainder.

## What Changes

- `k8s/monitoring/dashboards/llm-stack.json` gets the panel "Latency per Output Token (p50 / p95) per Deployment" in the Latency row, beside "Time to First Token p95 per Model". The panel shows the p50 and p95 of the gateway's histogram `litellm_deployment_latency_per_output_token` for each `api_base` and `litellm_model_name`. Its description says what LiteLLM 1.103.0 measures. The three panels of the row are each eight columns wide.
- `src/devops_cli/ai/knowledge_base/it_domains/tools/ollama.md` gives `kubectl -n llm exec ds/<tier> -c ollama -- ollama ps`, which shows the loaded models, their size, their context and their expiry on one tier. It also records the keep-alive behaviour: a call through the gateway keeps the lease that `devops ai prewarm` set, and a model that a gateway call loads gets the default keep-alive of its tier. Its `applies_to` changes from `tool:ollama@0.6.*` to `tool:ollama@0.34.*`, the release line that the tiers run (`ollama/ollama:0.34.4` in `k8s/llm/profiles/ollama-profiles.yaml`).
- The docstring of `acquire_ollama_slot` in `src/devops_cli/ai/client/network.py` says that the lease counts in this process only, and why no lease across processes exists. Its behaviour does not change.
- The dashboard ships as a manifest: the `grafana-stack-dashboards` ConfigMap that Grafana loads. A manifest is observable, so the change carries a spec delta. No capability in `openspec/specs/` holds dashboard panels, so the delta creates the capability `llm-stack-dashboard`. The two texts change no behaviour.
- The change does not build the parts that Feasibility rejects.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `llm-stack-dashboard`: the panels of the LLM stack dashboard and the gateway series that each panel shows.

### Modified Capabilities

None.

## Impact

- Dashboard: `k8s/monitoring/dashboards/llm-stack.json`. Argo CD applies the new `grafana-stack-dashboards` ConfigMap, and Grafana loads the panel.
- Documents: `src/devops_cli/ai/knowledge_base/it_domains/tools/ollama.md`, and its `applies_to`, which now names the Ollama 0.34 releases that the tiers run.
- Code: the docstring of `acquire_ollama_slot` in `src/devops_cli/ai/client/network.py`.
- Tests: `tests/test_stack_dashboards.py` adds `test_llm_stack_dashboard_shows_latency_per_output_token_beside_time_to_first_token`.

## Feasibility

- **Time-per-output-token histogram: not built, the gateway exports one.** In the gateway pod (LiteLLM 1.103.0, read on 2026-10-24 with read-only commands), `set_llm_deployment_success_metrics` in `litellm/integrations/prometheus.py` observes `litellm_deployment_latency_per_output_token` for each successful call with more than zero `completion_tokens`. The value is `(end_time - start_time) / completion_tokens` for a call that is not streamed, and `(completion_start_time - start_time) / completion_tokens` for a streamed call. Thus it includes the prompt time, the wait in the Ollama queue and any model load, and for a streamed call it divides the time to the first token. The histogram has the default buckets of the Prometheus client: the `le` values in Prometheus are 0.005 to 10 and `+Inf`. In Prometheus on 2026-10-24, the 24-hour count was 468 calls for `qwen3-coder:30b` on the 48gib-fast tier and 270 on the 64gib-standard tier. `histogram_quantile(0.5, ...)` over 6 hours gave 8.0 ms per token on the 48gib-fast tier. The 24-hour count of `litellm_llm_api_time_to_first_token_metric` was 0, so these calls were not streamed. The Grafana MCP `query_prometheus` ran the two queries of the new panel and returned data.
- **p50 and p95 in `devops ai cost report --by backend`: rejected.** The new panel shows them from the gateway's histogram, with Prometheus and Grafana (AGENTS.md rule 3).
- **`record_llm_metrics`: done.** v0.2.25 deleted it, and no file under `src/` or `tests/` names it.
- **`/api/ps` for each pod in `devops ai gateway status`: rejected.** On 2026-10-24, `kubectl -n llm exec ds/<tier> -c ollama -- ollama ps` on the four running tiers (Ollama 0.34.4) showed the columns `NAME`, `ID`, `SIZE`, `PROCESSOR`, `CONTEXT` and `UNTIL`. On `ollama-48gib-slow` it showed `qwen3-embedding:0.6b` and `qwen3.8:27b` with `UNTIL` "Forever".
- **Keep-alive on the chat bodies and `OLLAMA_KEEP_ALIVE` on each tier: rejected, the premise is false.** The issue said that a request without `keep_alive` resets the expiry to the server default.
  - A live test on 2026-10-24 on the idle 16gib tier, through a port-forward, with Ollama 0.34.4: a prewarm (`/api/generate` with `keep_alive: 1h`) set `expires_at` one hour later. `/api/chat` without `keep_alive`, blocking and streamed, and `/api/embed` without `keep_alive` each kept the one-hour lease. The test models were unloaded after the test.
  - Ollama v0.34.4 `server/sched.go`: `useLoadedRunner` sets `runner.sessionDuration` only `if pending.sessionDuration != nil`. `load` uses `envconfig.KeepAlive()` only when the request that loads a model sends no keep-alive. `processCompleted` sets `expiresAt` to the end of the call plus `sessionDuration`.
  - The gateway sends no `keep_alive`: `litellm/llms/ollama/chat/transformation.py` in the gateway pod adds `keep_alive` to the body only when the call or the model settings set it, and `k8s/llm/gateway/configmap.yaml` sets none.
- **Models that fit each pod: done** by #1061, #1064 and #1987. The tiers are in `k8s/llm/profiles/ollama-profiles.yaml`, and `k8s/llm/ollama.yaml` does not exist.
- **`acquire_ollama_slot` counts per process: still missing from the code.** Its docstring said nothing about the scope of the lease. The issue's constraint gives the reason: a lease across processes adds a hidden queue in front of the queue of Ollama (`OLLAMA_NUM_PARALLEL` 1), which repeats #467.
- On the base commit, `test_llm_stack_dashboard_shows_latency_per_output_token_beside_time_to_first_token` fails: no panel selects `litellm_deployment_latency_per_output_token_bucket`.

## Existing Tool Considered

LiteLLM's Prometheus callback exports the latency per output token, Prometheus stores it, and Grafana shows it. `ollama ps` shows the loaded models and their expiry, and Ollama's scheduler keeps the lease of a loaded model. Nothing is built: the change adds one dashboard panel and two texts. It deletes no internal code.

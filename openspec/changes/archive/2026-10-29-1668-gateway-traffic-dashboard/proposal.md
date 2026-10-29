# Proposal

## Why

Issue #1668: the AI spend dashboard reads only `devops_cli_ai_*`, which only devops-cli writes. A call that another client sends through the gateway does not show, and neither does an attempt that failed. The gateway cannot name its callers either: every caller sends the one master key, and the gateway puts no caller on its token series.

Measured on 2026-10-29 (read-only), over 7 days:

- The gateway answered 3,291 chat requests with status 200, and devops-cli's own series counted about 1,785 gateway chat calls. Open WebUI, an editor extension and other clients sent the rest.
- The gateway also counted 104 chat requests with status 499, 30 with 500 and 4 with 408, and 114 embedding requests with 499. No panel showed them.
- Every request series had `end_user="None"`. devops-cli's chat calls named `OpenAI/Python 3.26.1` as their user agent, refine's agent `pydantic-ai/2.54.0` and its embedding calls `python-httpx2/2.13.1`, so no user agent named devops-cli.

## What Changes

- **Caller headers.** Each devops-cli call to the gateway names its caller: the OTel `service.name` of the process in `x-litellm-end-user-id` (`devops-cli`, or the `OTEL_SERVICE_NAME` that a workload sets: `devops-cli-job`, `roadmap-service`), and `devops-cli/<release>` as its User-Agent.
  - Chat calls set them through the OpenAI client's `default_headers`, for the `gateway` provider only.
  - Embedding calls set them on the engine's client when the gateway serves the embeddings.
  - A pydantic-ai model that devops-cli sends to the gateway, as refine's investigation does, gets them from a request hook on its client.
  - A call to another provider names no end user.
- **One source of each value.** `otel_service_name()` in `telemetry/tracer.py` is the one place that reads `OTEL_SERVICE_NAME`. `user_agent()` in `http/client.py` is the one devops-cli User-Agent, and the broker uses it in place of its stale `devops-cli/0.2.9`.
- **The gateway names callers.** `k8s/llm/gateway/config.yaml` sets `litellm_settings.enable_end_user_cost_tracking_prometheus_only: true`, so LiteLLM writes the end-user id as the `end_user` label of its request and token series.
- **Open WebUI calls only the gateway.** `k8s/llm/values-open-webui.yaml` drops `ollamaUrls`, so the chart sets `ENABLE_OLLAMA_API=False`. Its RAG embeddings already go to the gateway (#1637).
- **The dashboard counts every caller.**
  - AI Requests in Range and Tokens Processed in Range take a call through the gateway from the gateway's series (2xx chat and embedding requests, and their tokens). devops-cli's series add only the calls that bypassed the gateway.
  - A new row, Gateway Traffic from Every Caller, shows the gateway's attempts by status, its replied requests and tokens by `end_user`, and the coverage stat: devops-cli's own count of its replied gateway calls over the gateway's.
  - The legends of Ollama Slot Wait by Priority (p95) name the priority with one pair of braces. Two pairs showed the braces.
- **Tests.**
  - Each gateway series that `ai-spend.json` reads must be in the LiteLLM capture, with every label that it matches or groups by, and must be read as a counter.
  - The rule that a panel states the limits of devops-cli's delta series applies only to panels that read such a series.
- **Docs.** `k8s/README.md` and `k8s/llm/profiles/README.md` say how the dashboard counts the gateway's callers, and that Open WebUI uses no Ollama Service.
- The headers, the dashboard and the manifests are behavior that a consumer observes, so the change carries a spec delta: the new capability `gateway-caller-telemetry`.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `gateway-caller-telemetry`: how the gateway's callers are named and counted, from the headers devops-cli sends to the panels of the AI spend dashboard that read the gateway's own series.

## Impact

- **Source:** `src/devops_cli/ai/client/network.py`, `ai/client/openai.py`, `ai/rag/embeddings.py`, `ai/providers/__init__.py`, `ai/pydantic_ai_bridge.py`, `http/client.py`, `http/broker.py` and `telemetry/tracer.py`.
- **Manifests and dashboard:** `k8s/llm/gateway/config.yaml`, `k8s/llm/values-open-webui.yaml` and `k8s/monitoring/dashboards/ai-spend.json`.
- **Docs:** `k8s/README.md` and `k8s/llm/profiles/README.md`.
- **Tests:** `tests/ai/client/test_gateway_caller_headers.py` (new), `tests/test_k8s_monitoring_dashboards.py`, `tests/test_stack_dashboards.py`, `tests/test_telemetry_instruments.py` and `tests/test_k8s_llm_gateway.py`.

## Feasibility

- **Gateway version:** the gateway runs `ghcr.io/berriai/litellm:v1.103.0`, in the manifest and live.
- **LiteLLM 1.103.0 source** (read from the PyPI wheel):
  - `x-litellm-end-user-id` is one of `STANDARD_CUSTOMER_ID_HEADERS` (`litellm/constants.py`), which `get_end_user_id_from_request_body` always reads first (`litellm/proxy/auth/auth_utils.py`).
  - `get_end_user_id_for_cost_tracking` returns it for Prometheus only when `enable_end_user_cost_tracking_prometheus_only` is `True` (`litellm/utils.py`).
  - No database is needed.
- **Live `/metrics` of the gateway** (read-only through the API service proxy):
  - `litellm_proxy_total_requests_metric_total` carries `route`, `status_code`, `end_user`, `user_agent` and `client_ip`.
  - `litellm_total_tokens_metric_total` carries `end_user`.
  - The capture `tests/fixtures/metrics/litellm.yaml` (2026-10-01, the same version) holds the same label names, so it needs no new capture.
- **Routes:** over 30 days, `/v1/chat/completions` and `/v1/embeddings` are the model calls. `/v1/models`, the model-info routes, `/health` and `route="None"` together had about 7 requests.
- **The label rename is no double count.** The issue saw gateway series with and without `k8s_cluster_name`. Measured with subqueries over 30 days, the old label set's last sample is 120 s before the new set's first, and both sets are present in one 5-minute step only. A counter's new series starts its `increase()` at its first sample, so a sum over both counts each request once, and no query needs a cluster matcher.
- **Open WebUI v0.11.4** (`backend/open_webui/routers/openai.py`):
  - It sets the body's `user` field only for a pipeline model, as an object. `_coerce_user_id_to_str` in LiteLLM drops an object, so no person's id becomes an `end_user` value. Pipelines are off here.
  - Its forwarded user headers are off by default, and LiteLLM does not read their names.
- **Open WebUI chart 16.6.0** (`templates/workload-manager.yaml`): with no `ollamaUrls` and `ollama.enabled: false`, it sets `ENABLE_OLLAMA_API=False`.
- **Client libraries:**
  - **openai 3.26.1:** `default_headers` merges the custom headers last (`_base_client.py`), so they replace the SDK's User-Agent.
  - **pydantic-ai 2.54.0:** it sets `User-Agent` in each request's `extra_headers` (`models/openai.py`), which replaces a client header. It has no public setter for a built model's settings. So its gateway client sets the headers in a request hook, which runs after the request is built.

## Existing Tool Considered

The change uses the tools that cover the need and builds none:

- **LiteLLM:** its own end-user tracking and Prometheus callback name and count the callers.
- **Client libraries:** the OpenAI SDK's `default_headers` and httpx2's request hooks carry the headers.
- **Grafana and Prometheus:** `label_replace` names the callers that send no end-user id.
- **Not used:** LiteLLM's virtual keys would name each caller by its key, but they need the gateway database (#1154), and the dashboard needs no key per caller.

The change deletes the hard-coded `devops-cli/0.2.9` User-Agent of the broker, and Open WebUI's direct `ollamaUrls`.

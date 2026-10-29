# Design

## The caller headers

Each call to the gateway sends two headers. `gateway_caller_headers()` in `ai/client/network.py` builds both, from one source each:

- **`x-litellm-end-user-id`** is the OTel `service.name` of the process (`otel_service_name()`): `devops-cli`, or the `OTEL_SERVICE_NAME` that a workload's manifest sets (`devops-cli-job` in `k8s/devops/cronjob.yaml`, `roadmap-service` in the Service's Deployment). The values are a closed set, so the `end_user` label stays small and names no person.
- **`User-Agent`** is `devops-cli/<release>` (`user_agent()` in `http/client.py`).

Each client library builds its requests differently, so each path sets the headers at the one point that its library does not override:

| Path | Library | Where the headers go |
| :--- | :--- | :--- |
| `LLMClient` chat calls, provider `gateway` | openai 3.26.1 | `default_headers` of the `openai.OpenAI` client. The SDK merges custom headers after its own User-Agent. |
| Embedding calls that the gateway serves | httpx2 | The `headers` of the engine's client, from `new_http_client`. The requests set only `Content-Type` and `Authorization`. |
| A pydantic-ai model sent to the gateway (refine's investigation) | pydantic-ai 2.54.0 over openai | A request hook on the provider's client, `name_gateway_caller`. pydantic-ai sets `User-Agent` in each request's `extra_headers`, so a client header would lose to it. |

A call to another provider names no end user. The User-Agent of those calls stays the library's own.

## The dashboard

- **AI Requests in Range** adds two parts:
  - the gateway's `/v1/chat/completions` and `/v1/embeddings` requests with a 2xx `status_code`;
  - devops-cli's `devops_cli_ai_requests_total{provider!="gateway", cached="false"}`.

  A gateway call is in the first part only. A cache answer is not a model call, and Response Cache Hit Share still shows it.
- **Tokens Processed in Range** adds two parts:
  - `litellm_total_tokens_metric_total`;
  - devops-cli's tokens with `provider!="gateway"`, `server!="cache"` and `type!="reasoning"`. A completion count already holds the reasoning tokens, as the gateway's total does.
- **Gateway Traffic from Every Caller** row:
  - attempts by `status_code`, every numeric status, so a 408 or a 5xx shows;
  - replied requests and tokens by `end_user`, with `None` shown as `unnamed`;
  - the coverage stat.

## Rejected alternatives

- **One request hook on every devops-cli client.** `LLMClient` shares a pooled client per client class and backend type, and the shared pools also serve providers other than the gateway, so a hook there would name devops-cli to every endpoint. Each path has a seam that its library supports.
- **Model settings for pydantic-ai.** `extra_headers` in a model's settings would keep pydantic-ai from setting its User-Agent. pydantic-ai 2.54.0 sets a built model's settings only in its constructor, and `infer_model` builds the model, so this would write the private `_settings`.
- **A per-user end-user id.** It would grow the label with each person and put names into Prometheus. The issue asks for a fixed mapping.
- **LiteLLM virtual keys.** They name each caller by its key, but need the gateway's database (#1154).
- **A cluster matcher on the gateway series.** The issue asked to sum without `cluster` and `k8s_cluster_name` against a double count. The two label sets do not overlap in time (see Feasibility), so no matcher is needed. The series of the devcontainer cluster's gateway are a second gateway's real calls, so they stay in the sums.
- **Keeping Open WebUI's direct Ollama connections.** A chat that Open WebUI sends to Ollama directly is on no series that the dashboard reads. In the 7 days the issue read, no such call came, and its embeddings already go to the gateway.
- **The delta-series limits on every panel with `increase(`.** `test_every_panel_counting_with_increase_states_its_limits` asks each such panel to state the limits of devops-cli's OTLP deltas (#792). Prometheus scrapes the gateway's counters whole, so a panel that reads only them states no such limit. A panel that also reads a devops-cli series still states them.

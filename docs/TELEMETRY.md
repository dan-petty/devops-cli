# DevOps CLI Telemetry & Distributed Tracing Reference

DevOps CLI instruments all CLI subcommands, background tasks, and AI pipeline stages
with distributed OpenTelemetry traces (`@trace_span`) and OTLP metrics.

---

## Prometheus Metric Instruments

Each command runs as its own short-lived process, so counters and histograms are sent
as OTLP deltas. The collector's `deltatocumulative` processor keeps each series' running
total per host (`instance`) before Prometheus stores it. `devops telemetry connect`
points devops-cli at the cluster's collector.

| Metric Name | Type | Unit | Description |
|---|---|---|---|
| `devops_cli_command_total` | Counter | `1` | Commands run, by command and status. |
| `devops_cli_command_duration_seconds` | Histogram | `s` | Command wall time, by command. |
| `devops_cli_review_duration_seconds` | Histogram | `s` | Review wall time, by target type. |
| `devops_cli_findings_total` | Counter | `1` | Review findings, by persona, severity and status. |
| `devops_cli_ai_requests_total` | Counter | `1` | LLM calls, by provider, model, server, serving backend and whether the cache answered. |
| `devops_cli_ai_tokens_total` | Counter | `1` | LLM tokens, by type (prompt or completion), provider, model, server and backend. |
| `devops_cli_ai_spend_usd_total` | Counter | `USD` | Approximate LLM spend, by provider, model, server and backend. |
| `devops_cli_ai_local_cost_equivalent_usd_total` | Counter | `USD` | Equivalent hosted cloud spend avoided by local model execution. |
| `devops_cli_rag_query_duration_ms` | Histogram | `ms` | RAG retrieval time, by stage: embedding, search, ranking, or total for the whole query. |
| `devops_cli_qdrant_retries_total` | Counter | `1` | Qdrant requests retried after a transient error, by operation and error type. |
| `devops_cli_project_releases_total` | Counter | `1` | Total project releases tracked. |
| `devops_cli_project_commits_total` | Counter | `1` | Project commits count by release. |
| `devops_cli_project_prs_total` | Counter | `1` | Project pull requests merged by release. |
| `devops_cli_project_ci_runs_total` | Counter | `1` | CI workflow runs by name, status and conclusion. |
| `devops_cli_project_items_total` | Counter | `1` | Project items by milestone, type, priority and state. |
| `devops_cli_project_release_interval_days` | Histogram | `d` | Days elapsed between consecutive project releases. |
| `devops_cli_project_traffic_views_total` | Counter | `1` | GitHub repository total page views count. |
| `devops_cli_project_traffic_views_uniques_total` | Counter | `1` | GitHub repository unique visitors count. |
| `devops_cli_project_traffic_clones_total` | Counter | `1` | GitHub repository total git clones count. |
| `devops_cli_project_traffic_clones_uniques_total` | Counter | `1` | GitHub repository unique cloners count. |
| `devops_cli_project_traffic_referrers_total` | Counter | `1` | GitHub repository traffic referrals count by referrer source. |
| `devops_cli_project_traffic_paths_total` | Counter | `1` | GitHub repository traffic page views by content path. |
| `devops_cli_project_stars_total` | Counter | `1` | GitHub repository stargazers count. |
| `devops_cli_project_forks_total` | Counter | `1` | GitHub repository forks count. |

---

## Distributed Tracing & W3C Context Propagation

- **Root Trace Context**: CLI delegate sets up root spans (`cli.<subcommand>`) with execution metadata.
- **W3C `traceparent` Injection**: Subprocess calls inject standard W3C `traceparent` headers into child process environments.
- **OTLP Exporter**: Spans and metrics go to the OpenTelemetry Collector at `telemetry.endpoint` (`DEVOPS_CLI_TELEMETRY_ENDPOINT`). When devops-cli's configuration names none, OpenTelemetry's own `OTEL_EXPORTER_OTLP_ENDPOINT` names it, else `http://localhost:4318`. `telemetry.enabled` (`DEVOPS_CLI_TELEMETRY_ENABLED`) turns export off. When the configuration cannot load, those two variables alone decide, and export stays off unless `DEVOPS_CLI_TELEMETRY_ENABLED` turns it on.

---

## LLM Span Attributes

LLM spans follow the OpenTelemetry GenAI semantic conventions, which live in `open-telemetry/semantic-conventions-genai` and have no tagged release. `src/devops_cli/telemetry/semconv_genai.json` pins them to commit `b31e9e8ea26ac1c086d3313d474e31d7c3f391ae`, resolved with weaver 0.26.1, and lists their current attribute keys, metric names and span types.

- **Inference spans**: `ai.llm.dispatch` and `ai.llm.stream` are CLIENT spans of the `gen_ai.inference.client` type. Both carry `gen_ai.operation.name` (`chat`), `gen_ai.provider.name` (`anthropic` for the `claude` provider, other provider ids unchanged) and `gen_ai.request.model`, plus `server.address` and `server.port` when one backend host served the request. Only `ai.llm.dispatch` carries the reply's usage (`gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`) and `gen_ai.response.model`. `ai.llm.stream` carries `gen_ai.request.stream` and `gen_ai.response.time_to_first_chunk` in seconds. Both carry `gen_ai.response.finish_reasons` with the reason the provider gave for the reply's end (`stop`, `length`, `content_filter` or `tool_call`), and leave it out when the provider gave none.
- **Wrapper spans**: `ai.llm.chat`, `ai.client.chat_structured` and `pydantic_ai.direct.*` are INTERNAL and set no operation, usage or response keys, so each request is counted once.
- **Private keys**: Anything the conventions do not define is written under `llm.*`, such as `llm.request.priority`, `llm.tokens_per_second` and `llm.usage.cost_usd`, never under `gen_ai.*`.
- **Check**: `tests/test_telemetry_semconv.py` reads every Python file under `src/devops_cli/`, comments and docstrings included. It fails on a quoted string starting with `gen_ai.` that is not a current attribute key or metric name in the snapshot, and on any f-string that builds one.
- **Refresh**: A person moves the pin with `devops telemetry semconv refresh --commit <sha>`, which needs weaver on PATH and network access, then fixes what the check reports. The gate never runs weaver.

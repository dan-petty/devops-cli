# DevOps CLI Telemetry & Distributed Tracing Reference

DevOps CLI instruments all CLI subcommands, background tasks, and AI pipeline stages
with distributed OpenTelemetry traces (`@trace_span`) and OTLP metrics.

---

## Prometheus Metric Instruments

Each command runs as its own short-lived process. An OpenTelemetry SDK `MeterProvider`
with `DELTA` aggregation temporality and `ExponentialBucketHistogramAggregation`
aggregates every counter, histogram, and gauge recording in memory over the command's
run and flushes one OTLP `/v1/metrics` batch when the command finishes (`shutdown()`).
`devops serve --service` is one long process, so it also flushes when each lane batch
ends. One flush runs at a time, so the deltas reach the collector in the order they
were collected.
The collector's `deltatocumulative` processor adds the deltas of each stream (its
resource, scope, metric and attributes) into a running total before Prometheus stores
it. Prometheus names a series by `service.name` (`job`), `service.instance.id`
(`instance`) and the metric's attributes. The `service.instance.id` is the host name,
which every command on the host shares. The standard `OTEL_RESOURCE_ATTRIBUTES` sets
another one: roadmap-service sets `service.instance.id=roadmap-service`, so a new pod
writes the series of the pod before it. A running total that starts again from zero,
for a new pod or for a stream that gets no delta for `max_stale` (`1h` in
`k8s/otel/values.yaml`), is a counter reset to `rate()` and `increase()`.
Prometheus 3 stores each histogram as a
native histogram under the instrument's own name, with no `_bucket`, `_sum` or
`_count` series; query it with `histogram_quantile`, `histogram_avg` and
`histogram_count`.
`devops telemetry connect` points devops-cli at the cluster's collector.

| Metric Name | Type | Unit | Description |
|---|---|---|---|
| `devops_cli_command_total` | Counter | `1` | Commands run, by command and status. |
| `devops_cli_command_duration_seconds` | Histogram | `s` | Command wall time, by command. |
| `devops_cli_review_duration_seconds` | Histogram | `s` | Review wall time, by target type. |
| `devops_cli_findings_total` | Counter | `1` | Review findings, by producer, severity and status. |
| `devops_cli_ai_requests_total` | Counter | `1` | LLM calls and embedding requests, by operation (chat or embeddings), provider, model, server, serving backend and whether the cache answered. |
| `devops_cli_ai_tokens_total` | Counter | `1` | LLM and embedding tokens, by operation (chat or embeddings), type (prompt or completion), provider, model, server, backend and local: true when a local model ran them. The AI spend dashboard prices local tokens as savings at the reference price that the Prometheus recording rule devops_cli:ai_reference_price_usd_per_token holds for their operation and type. |
| `devops_cli_ai_spend_usd_total` | Counter | `USD` | Approximate LLM and embedding spend, by operation, provider, model, server and backend. Each request that a model answers adds to it, and a local request adds 0. |
| `devops_cli_ai_json_repairs_total` | Counter | `1` | LLM JSON replies repaired after strict parsing failed, by entry point source. |
| `devops_cli_ai_gateway_slot_wait_seconds` | Histogram | `s` | Time a chat call to the LLM gateway waited in this process for one of the gateway's backend slots, by outcome: ok once it held one, or timeout. |
| `devops_cli_rag_query_duration_ms` | Histogram | `ms` | RAG retrieval time, by stage: embedding, search, ranking, or total for the whole query. |
| `devops_cli_qdrant_retries_total` | Counter | `1` | Qdrant requests retried after a transient error, by operation and error type. |
| `devops_cli_rag_points` | Gauge | `1` | Points stored in RAG vector collections, by collection. |
| `devops_cli_project_releases_total` | Gauge | `1` | Total project releases tracked. |
| `devops_cli_project_commits_total` | Gauge | `1` | Project commits count by release. |
| `devops_cli_project_prs_total` | Gauge | `1` | Project pull requests merged by release. |
| `devops_cli_project_ci_runs_total` | Gauge | `1` | CI workflow runs by name, status and conclusion. |
| `devops_cli_project_items_total` | Gauge | `1` | Project items by milestone, type, priority and state. |
| `devops_cli_project_release_interval_days` | Histogram | `d` | Days elapsed between consecutive project releases. |
| `devops_cli_project_traffic_views_total` | Gauge | `1` | GitHub repository total page views count. |
| `devops_cli_project_traffic_views_uniques_total` | Gauge | `1` | GitHub repository unique visitors count. |
| `devops_cli_project_traffic_clones_total` | Gauge | `1` | GitHub repository total git clones count. |
| `devops_cli_project_traffic_clones_uniques_total` | Gauge | `1` | GitHub repository unique cloners count. |
| `devops_cli_project_traffic_referrers_total` | Gauge | `1` | GitHub repository traffic referrals count by referrer source. |
| `devops_cli_project_traffic_paths_total` | Gauge | `1` | GitHub repository traffic page views by content path. |
| `devops_cli_project_stars_total` | Gauge | `1` | GitHub repository stargazers count. |
| `devops_cli_project_forks_total` | Gauge | `1` | GitHub repository forks count. |
| `devops_cli_upstream_service_status` | Gauge | `1` | Upstream cloud service operational status severity code (0=none/operational, 1=minor, 2=major, 3=critical) by service and indicator. |
| `devops_cli_upstream_component_status` | Gauge | `1` | Upstream cloud service component status code (0=operational, 1=degraded, 2=partial_outage, 3=major_outage) by service and component. |

No process sends local savings in USD. `devops_cli_ai_tokens_total{local="true"}`
counts the tokens that a local model ran, and the AI spend dashboard multiplies them
by the Prometheus recording rule `devops_cli:ai_reference_price_usd_per_token` in
`k8s/monitoring/prometheus-values.yaml`. The rule holds genai-prices' price of the
default reference model for each operation and token type, so the workstation and
the Service are priced at one reference. `ai.reference_model` and
`ai.reference_embedding_model` price only the local ledger that `devops ai cost`
reports.

---

## Distributed Tracing & W3C Context Propagation

- **Root Trace Context**: CLI delegate sets up root spans (`cli.<subcommand>`) with execution metadata.
- **No Argument Values**: The command spans describe the command line with the command (`cli.command`), its command path (`cli.command_path`, such as `devops config set`), the number of arguments (`cli.args_count`) and the names of the parameters (`cli.kwargs_keys`). They do not record the argument values. An argument can be a credential (`devops config set <key> <value>`), and a secret pattern does not find all credentials. For this reason, the command spans and the resource have no `process.command_line` and no `process.command_args`. The OpenTelemetry semantic conventions make these two attributes Opt-In, and give `process.command_line` to the full command line, not to the name of the command.
- **Subprocess Spans**: Each program that devops-cli runs gets a `subprocess.<program>` span with the name of the program (`process.executable.name`) and the number of its arguments (`process.args_count`). By default the span does not record the arguments, because a command such as `devops uv run` or `devops gh api` passes the arguments of a person on to the program. To record them for a debugging session, set `telemetry.capture_command_args` to `true` (`devops config set telemetry.capture_command_args true`). Then the span holds the arguments in `process.command_args`, each argument through the secret mask. The mask does not find all credentials, so set the option back to `false` after the session. A subprocess span never holds `process.command_line`.
- **Profile Span**: `devops telemetry profile` runs the command line that it gets under a `telemetry.profile` span. The span holds the command path of the profiled command (`cli.command_path`, such as `devops config set`) and the number of its other words (`cli.args_count`). It does not record the argument values, also when `telemetry.capture_command_args` is `true`. The profiled command runs as a program of devops-cli, so with that option on, its `subprocess.<program>` span under the profile span holds the arguments in `process.command_args`.
- **Usage Errors**: The message of a usage error quotes the arguments, such as `Got unexpected extra argument (<value>)` from the parser or a `typer.BadParameter` that a command raises. Thus the command spans record the class of the error (`error.type`) and the exit code (`cli.exit_code`), and not the message. The person sees the error box of Typer, and `devops_cli_command_total` counts the command with the status `error`.
- **W3C `traceparent` Injection**: Subprocesses, sandbox containers (`devops sandbox deploy`, `devops docker sandbox`, `devops test sandbox`) and commands run with `devops sandbox exec` receive the active span as `TRACEPARENT` in their environment (and `TRACESTATE` when one is set). A container's parent is its `sandbox.deploy` or `docker.workload_sandbox.run` span, and each exec's is its own `sandbox.exec` span. With telemetry disabled, nothing is added.
- **OTLP Exporter**: Spans and metrics go to the OpenTelemetry Collector at `telemetry.endpoint` (`DEVOPS_CLI_TELEMETRY_ENDPOINT`). When devops-cli's configuration names none, OpenTelemetry's own `OTEL_EXPORTER_OTLP_ENDPOINT` names it, else `http://localhost:4318`. `telemetry.enabled` (`DEVOPS_CLI_TELEMETRY_ENABLED`) turns export off. When the configuration cannot load, those two variables alone decide, and export stays off unless `DEVOPS_CLI_TELEMETRY_ENABLED` turns it on.

---

## LLM Span Attributes

LLM spans follow the OpenTelemetry GenAI semantic conventions, which live in `open-telemetry/semantic-conventions-genai` and have no tagged release. `src/devops_cli/telemetry/semconv_genai.json` pins them to commit `b31e9e8ea26ac1c086d3313d474e31d7c3f391ae`, resolved with weaver 0.26.1, and lists their current attribute keys, metric names and span types.

- **Inference spans**: `ai.llm.dispatch` and `ai.llm.stream` are CLIENT spans of the `gen_ai.inference.client` type. Both carry `gen_ai.operation.name` (`chat`), `gen_ai.provider.name` (`anthropic` for the `claude` provider, other provider ids unchanged) and `gen_ai.request.model`, plus `server.address` and `server.port` when one backend host served the request. Only `ai.llm.dispatch` carries the reply's usage (`gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`) and `gen_ai.response.model`. `ai.llm.stream` carries `gen_ai.request.stream` and `gen_ai.response.time_to_first_chunk` in seconds. Both carry `gen_ai.response.finish_reasons` with the reason the provider gave for the reply's end (`stop`, `length`, `content_filter` or `tool_call`), and leave it out when the provider gave none.
- **Wrapper spans**: `ai.llm.chat` and `ai.client.chat_structured` are INTERNAL and set no operation, usage or response keys, so each request is counted once.
- **Gateway slot wait**: A chat call to the LLM gateway first waits in the process for one of the gateway's backend slots. The wait is an INTERNAL `ai.llm.gateway_slot` span under the call's `ai.llm.dispatch` or `ai.llm.stream` span, with `llm.gateway.slots` and `llm.gateway.slot_wait_seconds`, and an observation of `devops_cli_ai_gateway_slot_wait_seconds`. The call's `llm.wall_seconds`, its time to first chunk and its spend's duration start once it holds the slot, so the wait is not counted as inference.
- **Private keys**: Anything the conventions do not define is written under `llm.*`, such as `llm.request.priority`, `llm.tokens_per_second` and `llm.usage.cost_usd`, never under `gen_ai.*`.
- **Check**: `tests/test_telemetry_semconv.py` reads every Python file under `src/devops_cli/`, comments and docstrings included. It fails on a quoted string starting with `gen_ai.` that is not a current attribute key or metric name in the snapshot, and on any f-string that builds one.
- **Refresh**: A person moves the pin with `devops telemetry semconv refresh --commit <sha>`, which needs weaver on PATH and network access, then fixes what the check reports. The gate never runs weaver.

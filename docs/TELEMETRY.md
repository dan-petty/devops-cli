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
Cluster job pods have unique instance names and export metrics only once when they exit.
PromQL functions like `increase()` and `rate()` drop series that contain only one sample.
To calculate these counters, the collector sets `export_created_metric: true` in
`k8s/otel/values.yaml`. Prometheus sets `enable-feature: created-timestamp-zero-ingestion`
in `k8s/monitoring/prometheus-values.yaml`. Prometheus then writes a zero-value sample at the
start timestamp of each series, so `increase()` calculates the full counter value.
A gauge holds a snapshot, such as a project metric that the roadmap Service sends
every 15 minutes. Prometheus finds a plain selector only within five minutes of a
sample, so a dashboard reads a gauge with `last_over_time(<metric>[$__range])`, and
no gauge name ends in `_total`, which Prometheus keeps for counters.
Prometheus 3 stores each histogram as a
native histogram under the instrument's own name, with no `_bucket`, `_sum` or
`_count` series; query it with `histogram_quantile`, `histogram_avg` and
`histogram_count`.
Each metric is an entry of `INSTRUMENTS` in
`src/devops_cli/telemetry/instruments.py`, which gives its kind, and is sent with
`emit()`. `tests/test_telemetry_instruments.py` fails on a metric that a module
writes by name.
`devops telemetry connect` points devops-cli at the cluster's collector.

| Metric Name | Type | Unit | Description |
|---|---|---|---|
| `devops_cli_command_total` | Counter | `1` | Commands run, by command and status. |
| `devops_cli_command_duration_seconds` | Histogram | `s` | Command wall time, by command. |
| `devops_cli_subcommand_duration_seconds` | Histogram | `s` | Subcommand wall time, by subcommand and status: ok or error. |
| `devops_cli_subprocess_duration_seconds` | Histogram | `s` | Wall time of a program that devops-cli ran, by program and status: ok or error. |
| `devops_cli_telemetry_tests_total` | Counter | `1` | Test points that devops telemetry test sent, to show that metrics reach the collector. |
| `devops_cli_ci_checks_total` | Counter | `1` | Checks that devops ci ran, by step and outcome: pass or fail. |
| `devops_cli_ci_gate_slot_wait_seconds` | Histogram | `s` | Time a devops ci run waited for a free gate slot before its checks started. |
| `devops_cli_review_duration_seconds` | Histogram | `s` | Review wall time, by target type. |
| `devops_cli_findings_total` | Counter | `1` | Review findings, by producer, severity and status. |
| `devops_cli_ai_requests_total` | Counter | `1` | LLM calls and embedding requests, by operation (chat or embeddings), provider, model, server, serving backend and whether the cache answered. |
| `devops_cli_ai_tokens_total` | Counter | `1` | LLM and embedding tokens, by operation (chat or embeddings), type (prompt or completion), provider, model, server, backend and local: true when a local model ran them. The AI spend dashboard prices local tokens as savings at the reference price that its constant reference_price_usd_per_token holds for their operation and type. |
| `devops_cli_ai_spend_usd_total` | Counter | `USD` | Approximate LLM and embedding spend, by operation, provider, model, server and backend. Each request that a model answers adds to it, and a local request adds 0. A hosted gateway call is priced at the deployment model that the gateway names, and its model label is the model that the client asked for, such as the route name. |
| `devops_cli_ai_json_repairs_total` | Counter | `1` | LLM JSON replies repaired after strict parsing failed, by entry point source. |
| `devops_cli_ai_gateway_slot_wait_seconds` | Histogram | `s` | Time a chat call to the LLM gateway waited in this process for one of the gateway's backend slots, by outcome: ok once it held one, or timeout. |
| `devops_cli_ai_ollama_slot_wait_seconds` | Histogram | `s` | Time a call to Ollama waited in this process for a slot on one of its nodes, by priority (high, normal or as_available) and outcome: ok once it held one, or timeout. |
| `devops_cli_ai_chat_duration_seconds` | Histogram | `s` | LLM chat call wall time, by provider and model, from the request to the reply. A gateway call's time includes its wait for a backend slot. |
| `devops_cli_ai_structured_attempts_total` | Counter | `1` | Structured-output attempts, by model and outcome: valid when the reply matched its schema, else invalid. Each invalid attempt but the last is retried. |
| `devops_cli_ai_prewarms_total` | Counter | `1` | devops ai prewarm runs, by model, evict (true when the run unloaded the model) and outcome: ok or failed. |
| `devops_cli_ai_gateway_probe_duration_seconds` | Histogram | `s` | Time a health probe of the LLM gateway took. |
| `devops_cli_ai_gateway_healthy` | Gauge | `1` | Whether the last health probe of the LLM gateway passed: 1, or 0. |
| `devops_cli_ai_gateway_failovers_total` | Counter | `1` | Failovers of a gateway model alias to its fallback, by virtual model and simulate: true for a simulated failover. |
| `devops_cli_ai_capability_gate_total` | Counter | `1` | Failovers to a model below the capability tier of their role, by role, model and decision: rejection when the gate refused it, or override when --force let it through. |
| `devops_cli_rag_query_duration_ms` | Histogram | `ms` | RAG retrieval time, by stage: embedding, search, ranking, or total for the whole query. |
| `devops_cli_qdrant_retries_total` | Counter | `1` | Qdrant requests retried after a transient error, by operation and error type. |
| `devops_cli_rag_points` | Gauge | `1` | Points stored in RAG vector collections, by collection. |
| `devops_cli_github_requests_total` | Counter | `1` | GitHub requests the rate limiter paced, each attempt and retry once, by resource: the rate limit resource the request spends, such as core, graphql or search. A gh command and a request of the GitHub session both count. |
| `devops_cli_github_throttle_wait_seconds` | Histogram | `s` | Time devops-cli waited before it sent a refused GitHub request again, by resource: one observation for each throttle. GitHub refused the request with a rate limit, or the GitHub session got a 5xx for a read. |
| `devops_cli_github_graphql_points_total` | Counter | `1` | GraphQL points that GitHub reported each answer cost in its rateLimit field. |
| `devops_cli_embedding_cache_lookups_total` | Counter | `1` | Embedding cache lookups, one for each text that an embedding request gets, by result: hit or miss. A hit names its tier: memory for the cache of the process, or valkey. |
| `devops_cli_embedding_cache_size` | Gauge | `1` | Embeddings that the memory cache of the process held after its last embedding request. |
| `devops_cli_rag_embedding_batch_size` | Gauge | `1` | Texts in each embedding request after the last change of the adaptive batch size. |
| `devops_cli_rag_embedding_batch_resizes_total` | Counter | `1` | Changes of the adaptive embedding batch size, by action: additive_increase after enough fast batches, or multiplicative_decrease after a slow or failed batch. |
| `devops_cli_rag_drift_score` | Gauge | `1` | Share of a project's files that changed, were added or were deleted since its last index, from its last drift check, by project. A drifted knowledge base scores 1. |
| `devops_cli_rag_drift_detected` | Gauge | `1` | Whether the last drift check of a project found drift in its files, its git head or its knowledge base: 1, or 0, by project. |
| `devops_cli_rag_investigations_total` | Counter | `1` | RAG context retrievals that finished, by outcome: found when they returned context, or empty. |
| `devops_cli_rag_stops_total` | Counter | `1` | Processes that turned RAG off for the rest of their run after an embedding failure. |
| `devops_cli_vulnerability_lookups_total` | Counter | `1` | Packages looked up in a vulnerability database, by source, status and batch: true when one batch request looked them up. |
| `devops_cli_threat_intel_lookups_total` | Counter | `1` | Domains that a threat-intelligence source was asked about, by source and status: ok, unavailable or failed. A domain that the cache answered is not counted. |
| `devops_cli_project_releases` | Gauge | `1` | Total project releases tracked. |
| `devops_cli_project_commits` | Gauge | `1` | Project commits count by release. |
| `devops_cli_project_prs` | Gauge | `1` | Project pull requests merged by release. |
| `devops_cli_project_ci_runs` | Gauge | `1` | CI workflow runs by name, status and conclusion. |
| `devops_cli_project_items` | Gauge | `1` | Roadmap items, the issues with a priority label, by milestone, state, type and priority. A label is empty when the item has no value for it. |
| `devops_cli_project_release_interval_days` | Histogram | `d` | Days elapsed between consecutive project releases. |
| `devops_cli_project_traffic_views` | Gauge | `1` | GitHub repository total page views count. |
| `devops_cli_project_traffic_views_uniques` | Gauge | `1` | GitHub repository unique visitors count. |
| `devops_cli_project_traffic_clones` | Gauge | `1` | GitHub repository total git clones count. |
| `devops_cli_project_traffic_clones_uniques` | Gauge | `1` | GitHub repository unique cloners count. |
| `devops_cli_project_traffic_referrers` | Gauge | `1` | GitHub repository traffic referrals count by referrer source. |
| `devops_cli_project_traffic_paths` | Gauge | `1` | GitHub repository traffic page views by content path. |
| `devops_cli_project_stars` | Gauge | `1` | GitHub repository stargazers count. |
| `devops_cli_project_forks` | Gauge | `1` | GitHub repository forks count. |
| `devops_cli_upstream_service_status` | Gauge | `1` | Upstream cloud service operational status severity code (0=none/operational, 1=minor, 2=major, 3=critical) by service and indicator. |
| `devops_cli_upstream_component_status` | Gauge | `1` | Upstream cloud service component status code (0=operational, 1=degraded, 2=partial_outage, 3=major_outage) by service and component. |

No process sends local savings in USD. `devops_cli_ai_tokens_total{local="true"}`
counts the tokens that a local model ran, and the AI spend dashboard multiplies them
by its hidden constant `reference_price_usd_per_token`. The constant holds
genai-prices' price of the default reference model for each operation and token
type, so every process and every time range is priced at one reference. A series
from before the `local` label that the gateway served counts as local, and a series
from before the `operation` label counts as chat. `ai.reference_model` and
`ai.reference_embedding_model` price the local ledger that `devops ai cost` reports.
Their defaults are the references of the dashboard.

---

## Distributed Tracing & W3C Context Propagation

- **Root Trace Context**: CLI delegate sets up root spans (`cli.<subcommand>`) with execution metadata.
- **No Argument Values**: The command spans describe the command line with the command (`cli.command`), its command path (`cli.command_path`, such as `devops config set`), the number of arguments (`cli.args_count`) and the names of the parameters (`cli.kwargs_keys`). They do not record the argument values. An argument can be a credential (`devops config set <key> <value>`), and a secret pattern does not find all credentials. For this reason, the command spans and the resource have no `process.command_line` and no `process.command_args`. The OpenTelemetry semantic conventions make these two attributes Opt-In, and give `process.command_line` to the full command line, not to the name of the command.
- **Subprocess Spans**: Each program that devops-cli runs gets a `subprocess.<program>` span with the name of the program (`process.executable.name`) and the number of its arguments (`process.args_count`). By default the span does not record the arguments, because a command such as `devops uv run` or `devops gh api` passes the arguments of a person on to the program. To record them for a debugging session, set `telemetry.capture_command_args` to `true` (`devops config set telemetry.capture_command_args true`). Then the span holds the arguments in `process.command_args`, each argument through the secret mask. The mask does not find all credentials, so set the option back to `false` after the session. A subprocess span never holds `process.command_line`.
- **Profile Span**: `devops telemetry profile` runs the command line that it gets under a `telemetry.profile` span. The span holds the command path of the profiled command (`cli.command_path`, such as `devops config set`) and the number of its other words (`cli.args_count`). It does not record the argument values, also when `telemetry.capture_command_args` is `true`. The profiled command runs as a program of devops-cli, so with that option on, its `subprocess.<program>` span under the profile span holds the arguments in `process.command_args`.
- **LLM Content Gating**: Native AI inference spans (`ai.llm.dispatch`) omit `llm.prompt_preview` and `llm.response_preview` by default, and Logfire configures `instrument_pydantic_ai(include_content=False)` and scrubs private host patterns. To record prompt and response previews for debugging, set `telemetry.capture_llm_content` to `true` (`devops config set telemetry.capture_llm_content true`).
- **Usage Errors**: The message of a usage error quotes the arguments, such as `Got unexpected extra argument (<value>)` from the parser or a `typer.BadParameter` that a command raises. Thus the command spans record the class of the error (`error.type`) and the exit code (`cli.exit_code`), and not the message. The person sees the error box of Typer, and `devops_cli_command_total` counts the command with the status `error`.
- **Reported Failures**: A command that prints its own error and exits with a non-zero code is counted one time in `devops_cli_command_total`, with the status `error`. Its command span records the exit code in `cli.exit_code`. devops-cli logs no record for that exit. The log export gets the records that the command logs and the record of an unhandled exception.
- **W3C `traceparent` Injection**: Subprocesses, sandbox containers (`devops sandbox deploy`, `devops docker sandbox`, `devops test sandbox`) and commands run with `devops sandbox exec` receive the active span as `TRACEPARENT` in their environment (and `TRACESTATE` when one is set). A container's parent is its `sandbox.deploy` or `docker.workload_sandbox.run` span, and each exec's is its own `sandbox.exec` span. With telemetry disabled, nothing is added.
- **OTLP Exporter**: Spans and metrics go to the OpenTelemetry Collector at `telemetry.endpoint` (`DEVOPS_CLI_TELEMETRY_ENDPOINT`). When devops-cli's configuration names none, OpenTelemetry's own `OTEL_EXPORTER_OTLP_ENDPOINT` names it, else `http://localhost:4318`. `telemetry.enabled` (`DEVOPS_CLI_TELEMETRY_ENABLED`) turns export off. When the configuration cannot load, those two variables alone decide, and export stays off unless `DEVOPS_CLI_TELEMETRY_ENABLED` turns it on.

---

## LLM Span Attributes

LLM spans follow the OpenTelemetry GenAI semantic conventions, which live in `open-telemetry/semantic-conventions-genai` and have no tagged release. `src/devops_cli/telemetry/semconv_genai.json` pins them to commit `b31e9e8ea26ac1c086d3313d474e31d7c3f391ae`, resolved with weaver 0.26.1, and lists their current attribute keys, metric names and span types.

- **Inference spans**: `ai.llm.dispatch` and `ai.llm.stream` are CLIENT spans of the `gen_ai.inference.client` type. Both carry `gen_ai.operation.name` (`chat`), `gen_ai.provider.name` (`anthropic` for the `claude` provider, other provider ids unchanged) and `gen_ai.request.model`, plus `server.address` and `server.port` when one backend host served the request. Only `ai.llm.dispatch` carries the reply's usage (`gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`) and `gen_ai.response.model`. `ai.llm.stream` carries `gen_ai.request.stream` and `gen_ai.response.time_to_first_chunk` in seconds. Both carry `gen_ai.response.finish_reasons` with the reason the provider gave for the reply's end (`stop`, `length`, `content_filter` or `tool_call`), and leave it out when the provider gave none.
- **Wrapper spans**: `ai.llm.chat` and `ai.client.chat_structured` are INTERNAL and set no operation, usage or response keys, so each request is counted once.
- **Gateway slot wait**: A chat call to the LLM gateway first waits in the process for one of the gateway's backend slots. The wait is an INTERNAL `ai.llm.gateway_slot` span under the call's `ai.llm.dispatch` or `ai.llm.stream` span, with `llm.gateway.slots` and `llm.gateway.slot_wait_seconds`, and an observation of `devops_cli_ai_gateway_slot_wait_seconds`. The call's `llm.wall_seconds`, its time to first chunk and its spend's duration start once it holds the slot, so the wait is not counted as inference.
- **Ollama slot wait**: A call to Ollama first waits in the process for a slot on one of its nodes, queued by priority: `high` first, `as_available` last. Each call observes its wait once in `devops_cli_ai_ollama_slot_wait_seconds`, by `priority` and by `outcome`: `ok` once it holds a slot, or `timeout` when its deadline passes with no slot. A call that finds a free slot observes about 0 s, so the quantiles cover every call.
- **Private keys**: Anything the conventions do not define is written under `llm.*`, such as `llm.request.priority`, `llm.tokens_per_second` and `llm.usage.cost_usd`, never under `gen_ai.*`.
- **Check**: `tests/test_telemetry_semconv.py` reads every Python file under `src/devops_cli/`, comments and docstrings included. It fails on a quoted string starting with `gen_ai.` that is not a current attribute key or metric name in the snapshot, and on any f-string that builds one.
- **Refresh**: A person moves the pin with `devops telemetry semconv refresh --commit <sha>`, which needs weaver on PATH and network access, then fixes what the check reports. The gate never runs weaver.

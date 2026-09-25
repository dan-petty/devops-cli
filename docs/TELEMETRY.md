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
| `devops_cli_rag_query_duration_ms` | Histogram | `ms` | RAG retrieval time. |

---

## Distributed Tracing & W3C Context Propagation

- **Root Trace Context**: CLI delegate sets up root spans (`cli.<subcommand>`) with execution metadata.
- **W3C `traceparent` Injection**: Subprocess calls inject standard W3C `traceparent` headers into child process environments.
- **OTLP Exporter**: Spans are emitted to OpenTelemetry Collector via `DEVOPS_CLI_OTEL_ENDPOINT` (`http://localhost:4318/v1/traces`).

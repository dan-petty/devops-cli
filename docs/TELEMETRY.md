# DevOps CLI Telemetry & Distributed Tracing Reference

DevOps CLI instruments all CLI subcommands, background tasks, and AI pipeline stages
with distributed OpenTelemetry traces (`@trace_span`) and in-memory Prometheus metrics (`GLOBAL_METRICS`).

---

## Prometheus Metric Instruments

| Metric Name | Type | Description |
|---|---|---|
| `devops_cli_command_duration_seconds` | Histogram | CLI execution latency waterfall in seconds by subcommand. |
| `devops_cli_command_total` | Counter | Total CLI command invocations partitioned by status and command group. |
| `devops_cli_subprocess_duration_seconds` | Histogram | Subprocess execution latency in seconds across external binaries. |
| `devops_cli_subprocess_total` | Counter | Total external tool executions partitioned by binary and exit status. |
| `devops_cli_ai_llm_requests_total` | Counter | Total AI / LLM completions dispatched by provider and model. |
| `devops_cli_ai_token_usage_total` | Counter | Cumulative input and output token consumption across review stages. |
| `devops_cli_security_findings_total` | Counter | Total security vulnerabilities and anti-patterns flagged by scanner. |
| `devops_cli_cache_hits_total` | Counter | Semantic cache hits for embeddings and AI review prompt hashes. |
| `devops_cli_cache_misses_total` | Counter | Semantic cache misses triggering fresh LLM inference requests. |

---

## Distributed Tracing & W3C Context Propagation

- **Root Trace Context**: CLI delegate sets up root spans (`cli.<subcommand>`) with execution metadata.
- **W3C `traceparent` Injection**: Subprocess calls inject standard W3C `traceparent` headers into child process environments.
- **OTLP Exporter**: Spans are emitted to OpenTelemetry Collector via `DEVOPS_CLI_OTEL_ENDPOINT` (`http://localhost:4318/v1/traces`).

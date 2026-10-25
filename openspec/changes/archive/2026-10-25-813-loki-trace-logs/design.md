# Design

## Context

See proposal.md - Why. `OTelTelemetryClient` currently exports traces to `/v1/traces` and metrics to `/v1/metrics` via `_send_payload`. `TraceCorrelationFilter` in `src/devops_cli/telemetry/logging_bridge.py` injects active `trace_id` and `span_id` onto Python standard logging `LogRecord` instances. The OpenTelemetry collector forwards logs to Loki via `otlp_http/loki`, and Tempo is deployed as Grafana datasource `tempo`.

## Goals / Non-Goals

**Goals:**
- Export standard library log records of level WARNING and above to the OpenTelemetry collector `/v1/logs` endpoint using OTLP JSON.
- Attach the active `trace_id` and `span_id` to each exported log record.
- Mask secrets and strip prompt and reply content from log records (#606).
- Configure Grafana Loki datasource to extract trace IDs and link them directly to Tempo.
- Add an error stream panel to `devops-cli.json` for viewing devops-cli warning and error logs.

**Non-Goals:**
- Exporting INFO or DEBUG logs to Loki.
- Modifying Logfire telemetry integration.

## Decisions

### 1. Capture WARNING and ERROR logs with an OTel logging handler

`OTelLoggingHandler` derives from `logging.Handler` and listens for records at `logging.WARNING` and above. When `OTelTelemetryClient` initializes with telemetry enabled, it attaches this handler to the root logger. When the client shuts down, it removes the handler to maintain test isolation.

### 2. Route OTLP log exports through the tracer background executor

Log records format into OTLP JSON `resourceLogs` payloads and export through `_send_payload("/v1/logs", payload)`. This reuses the existing worker pool, dry-run suppression, and failure accounting. Queued log exports drain automatically when `tracer.flush()` runs at command completion.

### 3. Re-entrancy protection and recursive suppression

To prevent infinite logging loops when an export fails or logs an internal message:
- The handler ignores log records originating from the `devops_cli.telemetry` package.
- A thread-local guard prevents recursive invocation inside `emit()`.

### 4. Mask secrets and omit LLM prompt and reply content

The handler applies `mask_secrets()` to log message bodies and exception traces. Any record attributes matching prompt, completion, or reply keywords are omitted, complying with issue #606.

### 5. Link Loki logs to the deployed Tempo datasource

The Loki datasource definition in `k8s/monitoring/grafana-values.yaml` adds `derivedFields` targeting `datasourceUid: tempo`. The regular expression matches `trace_id` or `traceId` in log lines and JSON payloads.

### 6. Add error stream logs panel in devops-cli dashboard

A new panel of type `logs` is added to `k8s/monitoring/dashboards/devops-cli.json` titled "devops-cli Error Stream". It queries Loki with `{service_name="devops-cli"}`.

## Rejected Alternatives

- **Use OTel BatchLogRecordProcessor with an independent HTTP client.** Rejected: `tracer.py` already manages an asynchronous background thread pool, dry-run suppression, and failure counters. Running an independent processor and client duplicates connection management, background threads, and error accounting.
- **Export INFO and DEBUG logs to Loki by default.** Rejected: The acceptance criteria in issue #813 specifically call for WARNING and above. High-volume info and debug logs from CLI operations would flood Loki without actionable diagnostic value.
- **Point Loki derived field to Jaeger.** Rejected: Jaeger was deleted from the monitoring stack (#1624, #2036). The active trace datasource in Grafana is Tempo (`datasourceUid: tempo`). Linking to Jaeger would produce broken links.

## Risks / Trade-offs

- [Risk: Recursion when log emission fails] → Mitigation: Re-entrancy guard in the logging handler and ignore logs from `devops_cli.telemetry`.
- [Risk: Sensitive data or prompt content leaks to Loki] → Mitigation: Sanitize log messages with `mask_secrets` and drop prompt and reply attributes.

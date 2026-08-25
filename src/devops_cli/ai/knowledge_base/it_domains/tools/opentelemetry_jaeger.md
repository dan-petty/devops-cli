# Knowledge Base: OpenTelemetry & Jaeger (Distributed Tracing & APM)

## 1. Overview & Purpose

OpenTelemetry (OTel) is an open-source observability framework providing vendor-agnostic APIs, SDKs, and tooling to generate, collect, and export telemetry data (traces, metrics, logs). Jaeger is an open-source distributed tracing platform used for monitoring and troubleshooting microservices-based distributed systems. In the `devops-cli` ecosystem, OpenTelemetry instruments all CLI commands, subcommands, subprocesses, and REST endpoints with distributed trace spans and exports them to local OTLP collectors and Jaeger.

---

## 2. Usage Information & Architecture

- **Automatic Instrumentation Engine**: Integrated directly into `src/devops_cli/telemetry/tracer.py`:
  - `trace_span(name, attributes)`: Context manager generating 16-hex span IDs and 32-hex trace IDs.
  - `OTelTelemetryClient`: High-performance non-blocking client with pooled HTTP transport and fallback buffering.
- **W3C Trace Context**: Supports W3C `traceparent` headers (`00-<trace_id>-<span_id>-01`) for end-to-end trace correlation across subprocesses and HTTP services.
- **CLI Subcommand**: `devops telemetry` (or `devops otel`) provides connection probes, trace health checks, and OTLP endpoint configuration.

---

## 3. Common & Advanced Commands

### DevOps CLI Telemetry Commands
```bash
# Test connection to OTLP telemetry collector / Jaeger
devops telemetry test

# Show telemetry configuration and active endpoint
devops telemetry status

# Emit a test trace span and verify collector reception
devops telemetry probe
```

### Standard & Advanced OTel & Jaeger Commands
```bash
# Port-forward Jaeger UI to local port 16686
kubectl port-forward svc/jaeger-query -n monitoring 16686:16686

# Port-forward OTLP HTTP receiver (port 4318)
kubectl port-forward svc/jaeger-collector -n monitoring 4318:4318

# Send a manual OTLP trace span payload via curl
curl -X POST http://localhost:4318/v1/traces \
  -H "Content-Type: application/json" \
  -d '{
    "resourceSpans": [{
      "resource": {
        "attributes": [
          {"key": "service.name", "value": {"stringValue": "devops-cli"}}
        ]
      },
      "scopeSpans": [{
        "scope": {"name": "devops-cli-tracer"},
        "spans": [{
          "traceId": "4bf92f3577b34da6a3ce929d0e0e4736",
          "spanId": "00f067aa0ba902b7",
          "name": "cli.manual-test",
          "kind": 1,
          "startTimeUnixNano": 1724500000000000000,
          "endTimeUnixNano": 1724500001000000000,
          "status": {"code": "STATUS_CODE_OK"}
        }]
      }]
    }]
  }'
```

---

## 4. Best Practice Guidance

1. **Semantic Conventions**: Adhere strictly to OpenTelemetry semantic conventions for attribute names:
   - `cli.command`: Root command name (e.g. `serve`, `review`).
   - `subprocess.bin`: Target subprocess executable (e.g. `kubectl`, `uv`).
   - `http.method`, `http.status_code`, `http.route`: HTTP request attributes.
2. **Error Capture**: When exceptions occur inside a span, record `exception.type`, `exception.message`, `exception.stacktrace`, and set span status code to `STATUS_CODE_ERROR`.
3. **Non-Blocking Telemetry**: Telemetry emission must never block or crash core CLI execution; handle network connection failures defensively.
4. **Context Propagation**: Pass `traceparent` through environment variables or HTTP headers when spawning child processes or REST calls.

---

## 5. Security Recommendations & Zero-Trust Policies

- **Attribute Sanitization**: Never attach sensitive credentials, passwords, auth tokens, or private keys to span attributes or events.
- **Egress Destination Validation**: Validate OTLP endpoint URLs against SSRF risks before dispatching trace payloads.

---

## 6. General Standards & Reference Guidelines

- **Standard Ports**:
  - `4317`: OTLP gRPC receiver.
  - `4318`: OTLP HTTP JSON/Protobuf receiver.
  - `16686`: Jaeger Query & Web UI.
- **Service Naming**: Set `service.name` to `devops-cli` (or child workspace name) across all trace spans.

---

## 7. Official References & Published Artifacts

- **Project Homepage**: [opentelemetry.io](https://opentelemetry.io/)
- **Jaeger Homepage**: [jaegertracing.io](https://www.jaegertracing.io/)
- **Public Git Repositories**:
  - [github.com/open-telemetry/opentelemetry-python](https://github.com/open-telemetry/opentelemetry-python)
  - [github.com/jaegertracing/jaeger](https://github.com/jaegertracing/jaeger)
- **Published Container Image**: [hub.docker.com/r/jaegertracing/all-in-one](https://hub.docker.com/r/jaegertracing/all-in-one)
- **DevOps CLI Telemetry Client**: [src/devops_cli/telemetry/tracer.py](../../../../telemetry/tracer.py)

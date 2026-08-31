# Code Library: OpenTelemetry & Jaeger (Distributed Tracing & APM)

## 1. Project References

| Resource | Endpoint / URL |
| :--- | :--- |
| **Official Documentation** | [opentelemetry.io/docs/languages/python/](https://opentelemetry.io/docs/languages/python/) • [jaegertracing.io](https://www.jaegertracing.io/) |
| **Public Git Repository** | [github.com/open-telemetry/opentelemetry-python](https://github.com/open-telemetry/opentelemetry-python) |
| **Official PyPI Package** | [pypi.org/project/opentelemetry-exporter-otlp-proto-grpc](https://pypi.org/project/opentelemetry-exporter-otlp-proto-grpc/) (`1.44.0`) |
| **DevOps CLI Integration** | [`src/devops_cli/telemetry/tracer.py`](file:///workspaces/devops-cli/src/devops_cli/telemetry/tracer.py) • [`src/devops_cli/commands/telemetry.py`](file:///workspaces/devops-cli/src/devops_cli/commands/telemetry.py) |

---

## 2. General Information & Architecture

**OpenTelemetry (OTel)** is the vendor-neutral CNCF standard for distributed tracing, metrics, and application observability. The OpenTelemetry Python SDK instruments function calls, HTTP requests, and multi-agent stage pipelines, emitting span telemetry over gRPC/OTLP to Jaeger and OpenTelemetry Collectors.

In `devops-cli`:
- **Distributed Spans**: Every CLI subcommand, AI persona review phase, and security scan stage is wrapped in `@trace_span` to capture duration, status, and semantic attributes.
- **Traceparent Propagation**: Automatically injects W3C `traceparent` headers into subprocess environments and outbound HTTP requests.
- **In-Memory Waterfall Profiling**: Powers `devops telemetry profile --last` to render terminal waterfalls and latency heatmaps directly in the console.

---

## 3. Comparable Projects & Tradeoffs

| Observability | Strengths | Weaknesses | Why `devops-cli` Chose OpenTelemetry |
| :--- | :--- | :--- | :--- |
| **`opentelemetry` (OTel)** | Vendor-neutral CNCF standard, unified traces/metrics, W3C context propagation, native Jaeger and Prometheus integration. | Requires setting up OTLP exporter pipelines. | **Selected**: The definitive open cloud-native standard for observability and distributed tracing. |
| **`datadog` / `newrelic` SDKs** | Proprietary APM integrations with automated SaaS dashboards. | Vendor lock-in, requires paid cloud accounts, cannot run in air-gapped homelabs. | Rejected: Violates open-source and local offline workstation design. |
| **Standard Library `logging`** | Simple unstructured text lines. | No hierarchical span waterfalls, no traceparent propagation, difficult to analyze multi-stage async latency. | Rejected: Insufficient for complex multi-agent pipeline profiling. |
| **Custom Stopwatch Timers** | Simple `time.perf_counter()`. | Ad-hoc, lacks standard distributed context propagation and Jaeger UI visualization. | Rejected: OTel provides standard OpenTracing compatibility. |

---

## 4. Key Concepts & Core Patterns

1. **`TracerProvider` & `BatchSpanProcessor`**: Coordinates span lifecycle and delivers batches to OTLP gRPC endpoints asynchronously.
2. **`@trace_span` Decorator & Context Manager**:
   ```python
   with trace_span("review.persona_review", attributes={"persona": "devsecops", "diff_lines": 120}):
       ...
   ```
3. **Traceparent Context**: Injects `traceparent: 00-{trace_id}-{span_id}-01` headers into subprocess environments for cross-process tracing.
4. **Jaeger UI**: Distributed trace waterfalls can be inspected at `http://localhost:16686`.

---

## 5. Common & Advanced Usage Examples

### Instrumenting Functions with `@trace_span`
```python
from devops_cli.telemetry.tracer import trace_span


@trace_span("k8s.deploy_stack", attributes={"stack": "infra"})
def deploy_infrastructure_stack(context: str | None = None) -> bool:
    # Function execution is automatically tracked as an OpenTelemetry span
    return True
```

### Inspecting Local Trace Waterfalls via CLI
```bash
# Render ASCII waterfall breakdown for the most recently executed CLI trace
devops telemetry profile --last

# Send a test telemetry span to verify local Jaeger connectivity
devops telemetry test-span
```

---

## 6. Best Practices & Security Standards

1. **Sanitize Span Attributes**: Never record secrets, passwords, or raw Bearer tokens in span attribute dictionaries.
2. **Graceful Exporter Fallback**: If Jaeger is not running locally, OTel gracefully suppresses network errors without blocking CLI operations.
3. **Granular Spans Over Monolithic Blocks**: Break multi-step operations into dedicated child spans to clearly expose latency bottlenecks.

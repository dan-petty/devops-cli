# Task 104: Telemetry Tracing Optimizations & Fixes

**Issue**: [#104](https://github.com/dan-petty/devops-cli/issues/104)
**Active Release Milestone**: `v0.2.15`
**Status**: Done
**Scope**: `k8s/otel/jaeger.yaml`, `src/devops_cli/telemetry/tracer.py`, `src/devops_cli/ai/rag/embeddings.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/config/settings.py`, `tests/test_telemetry.py`, `tests/test_rag_embeddings.py`

---

## 1. Description & Architectural Objectives

Comprehensive trace analysis of OpenTelemetry spans in Jaeger UI (`http://localhost:16687/search?end=1789071956083000&limit=1000&lookback=24h&maxDuration&minDuration&service=devops-cli&start=1788985556083000`) revealed four critical areas for performance optimization, stability improvement, and defect remediation:

### Key Deliverables
1. **Jaeger In-Memory Storage & OOMKilled Remediation**:
   - In `k8s/otel/jaeger.yaml`, `MEMORY_MAX_TRACES` was set to `50000` with a container memory limit of `512Mi`. Querying or accumulating traces caused pod OOMKills (`Exit Code: 137`).
   - Fix: Configure `MEMORY_MAX_TRACES: "10000"`, adjust `requests.memory: "256Mi"` and `limits.memory: "1024Mi"`, and apply to cluster.
2. **Telemetry Exception Span Hygiene**:
   - In `src/devops_cli/telemetry/tracer.py`, intentional CLI exit exceptions (`typer.Exit`, `click.exceptions.Exit`) with non-zero exit codes were routed to `handle.record_exception(exc)`. This generated full Python tracebacks as error events on normal validation exits, bloating span sizes and skewing error filters.
   - Fix: Only record full exception stack traces if `exit_code is None` and exception is not a handled exit. Handled exits set status to ERROR with message and exit code attribute without stack traces.
3. **RAG Embedding Fast Failover & Bounded Timeout**:
   - In `src/devops_cli/ai/rag/embeddings.py`, embedding queries defaulted to a 120s `httpx2` timeout. Stalled nodes blocked RAG query embedding for up to 2 minutes before failing over.
   - Fix: Bound embedding timeout to 15.0s max, enabling fast failover to candidate Ollama endpoints.
4. **Port-Forward Telemetry Ingestion Integration**:
   - Ensure `devops k8s port-forward` (and background services) forwards OTLP HTTP port 4318 alongside Jaeger query port 16686 so local spans are never dropped.
5. **Validation**:
   - Verify unit tests in `tests/test_telemetry.py` and `tests/test_rag.py`.
   - Ensure all quality gates pass via `devops ci`.

---

## 2. Implementation Progress

- [x] Trace analysis and root cause investigation on Jaeger UI.
- [x] Restored OTLP 4318 port-forward connectivity and verified span ingestion.
- [x] Ground issue in GitHub tracking (#104) with milestone `v0.2.15`.
- [x] Update `k8s/otel/jaeger.yaml` (`MEMORY_MAX_TRACES: 10000`, 1024Mi memory limit) and apply to Kubernetes cluster.
- [x] Refactor `tracer.py` exception span handling and verify in `tests/test_telemetry.py`.
- [x] Update `embeddings.py`, `defaults.py`, and `settings.py` with bounded timeout (`DEFAULT_RAG_EMBEDDING_TIMEOUT: 15.0`) and fast failover.
- [x] Author comprehensive unit tests in `tests/test_telemetry.py` and `tests/test_rag_embeddings.py`.
- [x] Run full `devops ci` quality gates (10/10 gates passed).
- [x] Atomic commit and push to `release/v0.2.15`.

# Task 319: OpenTelemetry W3C Traceparent Context Propagation, Metric SDK & Span Waterfall Optimization Research

**Issue**: [#319](https://github.com/dan-petty/devops-cli/issues/319)
**Status**: Done
**Milestone**: `v0.2.22`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/telemetry`, `priority/p1-high`

---

## 1. Description & Objectives

`run_subprocess` and `run_subprocess_async` both documented W3C trace context propagation
and both called `get_tracer().inject_trace_context(sub_env)` — a function that returns a
*copy* of the mapping it is given. Neither call site used the return value, so **no child
process ever received its parent span**. Every subprocess the CLI spawned began a fresh
root trace, and the only reason traces appeared connected at all was an inherited ambient
`TRACEPARENT` from whichever process sat at the top of the chain. The intervening spans
were orphaned, which is precisely the symptom the issue describes.

Two independent traceparent implementations also existed, in `telemetry/context.py` and on
the tracer client, and they disagreed about validity: one checked field lengths and ignored
the version, the other checked the version and ignored the lengths, and neither rejected
non-hexadecimal characters or the all-zero ids the specification forbids. Since one of the
carriers is the process environment, a malformed ambient value was carried into trace ids
and exported as though it were real.

### Key Deliverables Completed:

- [x] **Single W3C Implementation (`src/devops_cli/telemetry/propagation.py`)**:
  - `TraceContext` with strict `parse_traceparent`, covering version (`ff` reserved),
    field count, lowercase-hex form, all-zero ids, and forward compatibility with later
    versions whose extra fields must be ignored rather than rejected.
  - Invalid input returns `None` rather than raising: the value arrives from a caller's
    headers or the ambient environment, and the correct response to a malformed upstream
    context is to start a new trace, not to fail the operation that carried it.
  - `sanitize_tracestate` trims to the 32 list members the specification permits, since
    forwarding an oversized header breaks the next hop rather than this one.
- [x] **Separate Carriers for Headers and Environments**:
  - HTTP headers use lowercase `traceparent` and are injected into a **copy**.
  - Process environments use uppercase `TRACEPARENT` and are injected **in place**, because
    the caller already holds the environment it is about to hand to the child — returning a
    copy is exactly how the context came to be dropped.
  - Injection removes any inherited value under the other spelling. Extraction accepts both,
    so leaving one in place would let a grandparent's context shadow the one being injected.
- [x] **Subprocess Propagation Fixed**: `inject_trace_env` on the tracer client, used by both
  `run_subprocess` and `run_subprocess_async`. A child is now parented to the span that
  spawned it.
- [x] **Validated Adoption of Inherited Context**: `_resolve_parent` applies an explicit
  precedence — caller-supplied context, then explicit ids, then the span open on this
  thread, then the process environment — and validates the inherited value before adopting
  it. Extracting this also cleared a pre-existing complexity breach in `span` ($M=13$).
- [x] **Thread Propagation**: `ContextPropagatingThread` passes a context snapshot to the
  native `Thread(context=...)` parameter, and `bind_context` binds a callable to the
  *caller's* context for pools this module does not own. The snapshot must be taken on the
  calling thread; a helper that copied inside the worker would capture the worker's own
  empty context and propagate nothing.
- [x] **Bounded Ring Buffer**: the completed-span buffer is a `deque(maxlen=...)`. The list
  it replaced used `pop(0)`, shifting every retained span on each append once full, so the
  cost of recording a span grew with the retention limit exactly when spans arrived fastest.
- [x] **Centralized Constants**: traceparent version and reserved version, field lengths,
  flag values, header and environment variable names, tracestate member cap, span buffer size.
- [x] **Automated Tests & Quality Gates**:
  - 71 tests in `tests/test_trace_propagation.py` using structural tuple equality assertions,
    including a 17-case parametrised suite of malformed traceparents.
  - `propagation.py` at **100%** coverage, `context.py` at **98%**.
  - Cyclomatic complexity $M \le 10$ and nesting depth $\le 5$ across all touched modules.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

## Verification Results

- `uv run devops ci` — all gates pass (tests, coverage $\ge 90\%$, lint, format, mypy
  strict, audit, security, actionlint, docs, uv check, lockfile).
- The 71 pre-existing tests across `test_telemetry.py`, `test_telemetry_metrics.py`,
  `test_network_security_and_trace_correlation.py`, `test_sandbox_traces.py`,
  `test_otel_command_coverage.py` and `test_telemetry_cmd.py` pass unmodified.

## Design Constraint: The Propagation Defect Was Reproduced Before It Was Fixed

The bug survived because the only test of injection exercised the header path, where the
copying contract is correct. It was confirmed by capturing the environment actually handed
to `subprocess.run` and parsing it as a child process would, and
`test_a_subprocess_receives_the_active_span_as_its_parent` now asserts that environment
carries the spawning span. A related assertion pins the precedence rule: a freshly injected
context must win over one inherited from a grandparent, which is what stops a nested CLI
chain reporting every hop against the outermost span.

## Scope Note

**The OpenTelemetry Metrics SDK was not adopted.** `InMemoryMetricsRegistry` already
aggregates counters, gauges and histograms under a lock with bounded cardinality and
exports Prometheus text. Replacing it with the SDK would add a dependency and a second
aggregation path without changing what is recorded or exported; the defect in this area is
that the histogram exposition emits `_count` and `_sum` with no buckets, which is a
formatting bug better fixed against the exposition-format work rather than by swapping the
registry. **Baggage propagation for multi-persona review sessions** was also left out: the
W3C `baggage` header is a separate specification from trace context, and there is no
consumer in the codebase that reads baggage, so adding the carrier would ship an unexercised
code path.

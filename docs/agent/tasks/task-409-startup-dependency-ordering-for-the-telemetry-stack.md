# Task 409: Startup Dependency Ordering for the Telemetry Stack

**Issue**: [#409](https://github.com/dan-petty/devops-cli/issues/409)
**PR**: None (Draft)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/telemetry`, `priority/p2-medium`

---

## 1. Description & Objectives

The OpenTelemetry collector starts before Jaeger is accepting connections and logs a burst of `connection refused` against `jaeger.otel.svc.cluster.local:4317` until it recovers. The warnings are harmless and self-resolving, which is the problem: they are indistinguishable from a real outage when read later, and they were the first thing found when reviewing these logs.

#### Key Deliverables:
- Context & Rationale*: The OpenTelemetry collector starts before Jaeger is accepting connections and logs a burst of `connection refused` against `jaeger.otel.svc.cluster.local:4317` until it recovers. The warnings are harmless and self-resolving, which is the problem: they are indistinguishable from a real outage when read later, and they were the first thing found when reviewing these logs.
- Deliverable*: Express the dependency rather than retrying into the log — a readiness gate on the collector, or an explicit backoff that reports once rather than per attempt.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).

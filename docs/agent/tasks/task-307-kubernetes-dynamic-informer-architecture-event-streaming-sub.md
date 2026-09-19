# Task 307: Kubernetes Dynamic Informer Architecture, Event Streaming & Subprocess Elimination Research

**Issue**: [#307](https://github.com/dan-petty/devops-cli/issues/307)
**PR**: None (Draft)
**Status**: Backlog
**Milestone**: `v0.2.22`
**Priority**: `priority/p0-critical`
**Scope**: `type/feature`, `scope/k8s`, `priority/p0-critical`

---

## 1. Description & Objectives

Existing Kubernetes subcommands rely heavily on CLI `kubectl` subprocess invocations and fragmented synchronous calls, incurring high process spawning overhead and rigid error handling.

#### Key Deliverables:
- Context & Rationale*: Existing Kubernetes subcommands rely heavily on CLI `kubectl` subprocess invocations and fragmented synchronous calls, incurring high process spawning overhead and rigid error handling.
- Deep Integration & Functional Extension*: Integrate the official Python `kubernetes` client's asynchronous dynamic client, Informer watchers, and WebSocket streaming protocols to stream cluster events, pod status transitions, and container logs directly into in-memory queues without spawning external binaries.
- Code Optimization & Performance Acceleration*: Reduce Kubernetes status and pod polling latency from ~250ms per invocation to <10ms in-memory async I/O; implement client-side typed response caching with bounded TTLs; eliminate redundant JSON parsing of `kubectl get -o json` outputs.
- Refactoring Potential & Legacy Elimination*: Refactor `src/devops_cli/commands/k8s/` and runtime modules into a consolidated `KubernetesService` protocol; deprecate bespoke regex output scrubbers and procedural subprocess wrappers; ensure full POSIX process group isolation across any remaining external tools.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).

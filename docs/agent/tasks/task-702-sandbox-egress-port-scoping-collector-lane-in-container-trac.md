# Task 702: Sandbox Egress Port Scoping, Collector Lane & In-Container Trace Context

**Issue**: [#702](https://github.com/dan-petty/devops-cli/issues/702)
**Status**: Backlog
**Milestone**: `v0.2.24`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/telemetry`, `priority/p1-high`

---

## 1. Description & Objectives

Sandboxes default to `--network=none` (`src/devops_cli/sandbox/models.py:228,281`). `devops sandbox network-policy` (`commands/sandbox.py:1004`, MCP `ai/mcp/server.py:1400`) emits deny-all for isolated; namespace and whitelist modes add a kube-dns 53 rule, and whitelist modes add resolved `/32` `ipBlock`s (`models.py:189-221`) with no `ports`, so an entry's explicit port is discarded and every port to that IP opens. `run_subprocess` children get `TRACEPARENT` when tracing is on (`core/process.py:264,404`); containers do not: both env builders pass only `config.env` (`sandbox/engine.py:230`, `docker/sandbox.py:222-250`) and `exec_in_container` takes no environment (`docker/engine.py:401`). No lane reaches the OTel collector, and nothing counts blocked egress: no `alert:` rule, Alertmanager disabled (`k8s/monitoring/prometheus-values.yaml:71-72`), and squid-exporter documents no denied counter (`docs/squid-failover-and-observability.md:62-69`). vibes allows DNS, collector and cache lanes and pages on any blocked attempt.

#### Key Deliverables:
- **Deliverable**: In order. First, port scoping: keep the resolved-`/32` allowlist (vibes' `0.0.0.0/0 except RFC 1918` form admits every public host) and emit each entry's port, defaulting to TCP 443 for `https` or bare hosts and 80 for `http`. Second, an opt-in collector lane: `otel` namespaceSelector plus the collector's podSelector on TCP 4317/4318. No 6379 lane: the only Valkey (`k8s/llm/valkey.yaml:7`) backs the shared LLM cache, and the `llm` perimeter admits only its own namespace and `monitoring` (`k8s/llm/networkpolicy.yaml:23-31`). Third, container trace context: `get_tracer().inject_trace_env` (`telemetry/tracer.py:613`) on a copy of the env in both builders, and an `environment` parameter on `exec_in_container` forwarded to docker-py `exec_run`, with a fresh context per exec. Fourth, measure only: add the `squid` namespace to the Fluent Bit tail path (`k8s/logging/fluent-bit-values.yaml:30`) so `TCP_DENIED` rows from Squid's JSON log (`k8s/squid/configmap.yaml:155`) reach Loki for the planned 'whitelisted vs. blocked' panel of the v0.2.24 dashboard suite. No alert rule until Alertmanager is enabled. Distinct from the drafted 'Sandbox Enforcement Audit', which compares configuration to engine state.
- **Constraint**: A port-less rule is worse than it looks: an agent-supplied `https://host:8443` entry, via the MCP tool, opens every port and protocol to that host. A policy is only as real as the CNI: `devops k8s bootstrap` starts minikube with no `--cni` (`commands/k8s/cluster_runtime.py:94,99`) while its help claims Calico (`lang/en/help.py:260`); that false claim is a separate item, and until it is fixed a zero denial count proves nothing. Under `--network=none` a connect fails inside the container, so no host-side enforcer sees it; report such lanes as uncounted, never as zero. Select the collector by label, never a resolved `/32`.
- **Measured**: Whitelist entry `https://1.1.1.1:8443` yields a bare `1.1.1.1/32` rule with no `ports` (`.venv/bin/python -c "from devops_cli.sandbox.models import SandboxNetworkConfig as C; print(C(mode='public_whitelist', public_whitelist=['https://1.1.1.1:8443']).to_k8s_network_policy()['spec']['egress'])"`); 0 trace-context injections in the sandbox and docker packages (`grep -rn 'TRACEPARENT\|inject_env\|inject_trace_env' src/devops_cli/sandbox src/devops_cli/docker | wc -l`); 0 alerting rules (`grep -rn 'alert:' k8s | wc -l`).
- **Source**: vibes `patterns/zero-trust-sandboxing-and-observability.md`, `resources/k8s/agent-sandbox/network-policy.yaml`, `resources/observability/prometheus-agent-alerts.yaml`
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).

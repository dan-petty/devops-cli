# Proposal

## Why

Issue #2548: #1319 (PR #2541) made devops-cli send OTLP over HTTP only, so nothing in the `devops` namespace reaches the collector's gRPC port, 4317. The egress rule of `k8s/devops/networkpolicy.yaml` to the `otel` namespace still allowed TCP 4317 beside 4318. The rule opened more than the namespace needs, and #2541 made it stale.

## What Changes

- The egress rule of the `devops` perimeter to the `otel` namespace names the one port TCP 4318. Its comment says that devops-cli sends no OTLP over gRPC.
- A manifest test, `test_devops_egress_to_otel_admits_only_otlp_http`, fails when that rule names another port, and `test_perimeter_admits_no_ingress_and_exactly_four_egress_rules` expects the one port.
- The `otel` perimeter still admits 4317 from every namespace for other clients, and the collector and Tempo keep their gRPC receivers.
- A NetworkPolicy is observable, so the change carries a spec delta: an ADDED requirement in `otlp-export`.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `otlp-export`: the devops perimeter opens only OTLP/HTTP to the collector.

## Impact

- `k8s/devops/networkpolicy.yaml`, `tests/test_k8s_network_policies.py`, `tests/test_k8s_devops_runtime.py`.

## Feasibility

- On `origin/main` 8da35e60, `k8s/devops/configmap.example.yaml` names the collector at port 4318, no manifest under `k8s/devops/` sets `OTEL_EXPORTER_OTLP_PROTOCOL`, and `telemetry/logfire.py` sends to the Logfire HTTPS endpoint or hands its spans to the devops-cli tracer, so no pod of the namespace sends OTLP over gRPC. `rg 4317 k8s` finds no other egress rule for devops-cli: `k8s/otel/networkpolicy.yaml` admits 4317 from every namespace, and `k8s/otel/values.yaml` keeps the collector's and Tempo's gRPC receivers.
- `kubectl apply --dry-run=server -f k8s/devops/networkpolicy.yaml` accepts the changed policy, and `kubectl diff` shows only the removal of TCP 4317 from the egress to `otel`. Argo CD applies it after the merge; nothing is applied by hand.
- `k8s/README.md` says that the namespace reaches "the OpenTelemetry collector in namespace `otel`" and names no port, so it stays correct.

## Existing Tool Considered

A Kubernetes NetworkPolicy is the tool; the change removes one port from it and adds no code.

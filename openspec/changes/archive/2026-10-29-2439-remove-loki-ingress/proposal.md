# Proposal

## Why

Issue #2439: `k8s/ingress/ingress-routes.yaml` holds Ingress `loki-ingress`, which routes host `loki.<domain>` on the Traefik `web` entrypoint to Service `loki:3100` in namespace `logging`. The `logging-default-perimeter` NetworkPolicy admits port 3100 only from its own namespace, from Grafana and the Alloy collectors in `monitoring`, and from the OpenTelemetry Collector in `otel`. It has no peer for Traefik, so each request failed.

#1632 decided to keep the policy closed: a peer for Traefik would open the Loki API, with authentication disabled, to each client that reaches Traefik. It deleted the Ingress instead.

## What Changes

- Delete Ingress `loki-ingress` from `k8s/ingress/ingress-routes.yaml`.
- Add two invariant tests to `tests/invariants/test_k8s_manifests.py`: `test_no_ingress_routes_to_loki_in_the_logging_namespace` fails when `loki-ingress` is in the Ingress names, and `test_no_ingress_is_in_the_logging_namespace` fails when an Ingress under `k8s/` has `metadata.namespace` of `logging`.
- The manifest and the new invariant are observable, so the change has a spec delta: a new requirement of the `k8s-network-policies` capability.
- The change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `k8s-network-policies`: the logging perimeter admits no peer for Traefik, so no Ingress in the cluster targets namespace `logging`.

## Impact

- `k8s/ingress/ingress-routes.yaml`.
- `tests/invariants/test_k8s_manifests.py`.
- The live cluster after the merge: Argo CD removes Ingress `loki-ingress`.

## Feasibility

- `k8s/logging/networkpolicy.yaml`: the `logging-default-perimeter` policy's ingress rules admit port 3100 from `podSelector: {}`, from Grafana and the three Alloy collectors in `monitoring`, and from the OpenTelemetry Collector in `otel`, and from no Traefik pod.
- `k8s/ingress/ingress-routes.yaml` held `loki-ingress` with host `loki.<domain>`, class `traefik`, the `web` entrypoint, to Service `loki:3100` in namespace `logging`.
- No other file under `k8s/` holds an Ingress in namespace `logging`, and no document names `loki-ingress`.

## Existing Tool Considered

The invariant is a plain read of the manifests with `yaml.safe_load_all`, the same load that the `tests/support/k8s_tree.py::manifests()` helper already provides. The change builds no code and adds no dependency: it deletes a dead Ingress and adds two tests that read the tree with the existing `pytest` and `PyYAML`.

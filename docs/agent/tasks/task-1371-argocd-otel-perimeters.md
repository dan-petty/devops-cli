# Task: Argo CD and OTel Perimeters Ingress Hardening and Deploy-Stack Integration (#1371)

**Issue**: [#1371](https://github.com/dan-petty/devops-cli/issues/1371)
**Status**: Done
**Milestone**: v0.2.31
**Priority**: priority/p2-medium
**Scope**: scope/k8s, scope/security

## Description

Refactor and harden Kubernetes network policies for the `argocd` and `otel` namespaces, removing open `0.0.0.0/0` ingress CIDR blocks that inadvertently admitted all in-cluster pod traffic under kube-router, adding API server node access egress rules, and integrating both perimeters into the native `devops k8s deploy-stack` execution pipeline:

- **Argo CD Perimeter (`k8s/argocd/networkpolicy.yaml`)**:
  - Replace the open `ipBlock: 0.0.0.0/0` ingress rule on ports 8080 and 443 with the specific Traefik ingress controller peer (`kube-system`/`traefik`).
  - Add an egress `ipBlock` peer (`0.0.0.0/0` except `169.254.169.254/32`) on the API server rule (ports 443, 6443, 8443) so that Argo CD controller and repo-server components can reach the Kubernetes API server node IP across diverse cluster networking setups without being blocked.
  - Register `k8s/argocd/networkpolicy.yaml` in `_MANIFESTS_BY_STACK["infra"]` to provide a managed deployment path during `devops k8s deploy-stack --stack infra` (and `all`).

- **OpenTelemetry Perimeter (`k8s/otel/networkpolicy.yaml`)**:
  - Drop the open `ipBlock: 0.0.0.0/0` peer from ingress rule 2 (port 16686, Jaeger UI), keeping the Traefik, monitoring, and ingress namespace peers.
  - Add the Traefik peer to rule 4 on metrics port 8888, enabling the `otel-metrics-ingress` route to communicate with the collector through Traefik.
  - Register `k8s/otel/networkpolicy.yaml` in `_MANIFESTS_BY_STACK["infra"]` to ensure native stack deployments apply the perimeter even on clusters not running the Argo CD GitOps agent.

- **Guard Test and Exemptions**:
  - Delete `("argocd", "argocd-default-perimeter")` and `("otel", "otel-default-perimeter")` from `UNDEPLOYED_NETWORK_POLICIES` in `tests/test_k8s_network_policies.py`.
  - Add invariant unit tests pinning that neither policy defines ingress `ipBlock`s, that Argo CD's API-server egress permits port 6443 via an `ipBlock` peer, and that OTel metrics ingress admits Traefik on port 8888.

## Acceptance Criteria

- [x] Neither `argocd` nor `otel` perimeter has an ingress `ipBlock`, pinned by `test_ingress_admits_no_world_cidr`.
- [x] Argo CD's API-server egress admits 6443 through an `ipBlock` peer with metadata SSRF protection, pinned by `test_argocd_api_server_egress_admits_6443_through_ipblock`.
- [x] OTel rule 4 admits Traefik on port 8888, pinned by `test_otel_rule_4_admits_traefik_on_8888`.
- [x] A native deploy-stack applies both policies via `_MANIFESTS_BY_STACK["infra"]`, and the guard test's argocd and otel exemptions are removed from `UNDEPLOYED_NETWORK_POLICIES`.
- [x] `uv run devops ci` passes with 100% checks green and coverage >= 90%.
- Pending a person, on the homelab cluster:
  - `kubectl diff -f k8s/argocd/networkpolicy.yaml` and `kubectl diff -f k8s/otel/networkpolicy.yaml`, and settle each difference;
  - after the argocd policy applies, Argo CD stays Synced/Healthy: UI through Traefik, NodePort access, repo-server Git and Helm pulls, API server;
  - the Jaeger UI and `otel-metrics` routes answer through Traefik;
  - a pod in another namespace cannot reach 16686.

## Deliverables

- [x] `k8s/argocd/networkpolicy.yaml`: Replaced `0.0.0.0/0` ingress with Traefik peer and added `ipBlock` to API server egress.
- [x] `k8s/otel/networkpolicy.yaml`: Dropped `0.0.0.0/0` ingress from Jaeger UI and added Traefik peer to collector metrics rule.
- [x] `src/devops_cli/commands/k8s/stack_lifecycle.py`: Added `argocd/networkpolicy.yaml` and `otel/networkpolicy.yaml` to `_MANIFESTS_BY_STACK["infra"]`.
- [x] `tests/test_k8s_network_policies.py`: Removed exemptions from `UNDEPLOYED_NETWORK_POLICIES` and added acceptance criteria invariant tests.
- [x] `changelog.d/1371.md`: Added changelog fragment for release collation.
- [x] `docs/agent/tasks/task-1371-argocd-otel-perimeters.md`: Task documentation.

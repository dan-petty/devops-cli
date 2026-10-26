# Design

## Context

See `proposal.md` for motivation.
Kubernetes NetworkPolicies restrict network traffic through pod and namespace selectors.
In `k8s/llm/portkey/networkpolicy.yaml`, an ingress peer targets `kubernetes.io/metadata.name: devops-cli`.
In `k8s/otel/networkpolicy.yaml`, an ingress peer targets `kubernetes.io/metadata.name: ingress`.
Neither namespace exists in `k8s/namespaces.yaml` nor in the cluster runtime.

## Goals / Non-Goals

**Goals:**
- Remove the nonexistent `devops-cli` peer from `k8s/llm/portkey/networkpolicy.yaml`.
- Update the comment in `k8s/llm/portkey/networkpolicy.yaml` to match active peers.
- Remove the nonexistent `ingress` peer from `k8s/otel/networkpolicy.yaml`.
- Add an automated invariant test in `tests/test_k8s_network_policies.py` that verifies every `namespaceSelector` matches a declared or built-in namespace.

**Non-Goals:**
- Adding a new `devops-cli` or `ingress` namespace to `k8s/namespaces.yaml`.
- Changing egress rules or routes for Portkey or OpenTelemetry.

## Decisions

### Decision 1: Remove nonexistent namespace peers instead of creating dummy namespaces
- Rationale: Creating empty namespaces adds resource clutter and misleads maintainers. Portkey receives calls from stack workloads in `llm` and monitoring; OpenTelemetry Tempo receives ingress through Traefik in `kube-system` and monitoring. Neither requires `devops-cli` or `ingress`.
- Rejected Alternative: Adding `devops-cli` and `ingress` namespaces to `k8s/namespaces.yaml`.
  - Evidence: The cluster stack namespace is `devops`, not `devops-cli`. Ingress routing runs via Traefik in `kube-system`. Adding empty namespaces violates the principle of minimal resource footprint and preserves vestigial configuration.

### Decision 2: Add an offline invariant test in `tests/test_k8s_network_policies.py`
- Rationale: The repository tests Kubernetes manifests offline with `pyyaml`. The test loads `k8s/namespaces.yaml`, determines valid namespaces plus built-in namespaces (`kube-system`, `default`), scans all YAML manifests in `k8s/` for `namespaceSelector` blocks, and asserts that every `kubernetes.io/metadata.name` matches a valid namespace.
- Rejected Alternative: Running live cluster validation with `kubectl` or Kyverno CLI during test execution.
  - Evidence: AGENTS.md and `docs/TESTING.md` require tests to double external edges and run hermetically offline. Pytest file scanning runs in milliseconds without requiring cluster access or binary dependencies.

## Risks / Trade-offs

- [Risk] A future legitimate namespace is added but fails the test.
  → Mitigation: The test reads `k8s/namespaces.yaml` dynamically, so adding the namespace to `k8s/namespaces.yaml` automatically satisfies the test.

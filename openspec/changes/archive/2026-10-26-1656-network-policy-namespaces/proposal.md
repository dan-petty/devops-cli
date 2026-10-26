# Proposal

## Why

Two Kubernetes NetworkPolicies admit traffic from namespaces that do not exist (#1656).
NetworkPolicy `portkey-perimeter` admits traffic from namespace `devops-cli`, but the stack namespace is `devops`.
NetworkPolicy `otel-default-perimeter` admits traffic from namespace `ingress`, but Traefik runs in `kube-system`.
Correcting these peers aligns policy definitions with declared cluster namespaces and prevents misleading configurations.

This change fits in one pull request.

## What Changes

Manifests are observable cluster definitions and define access control rules:
- Remove the nonexistent `devops-cli` namespaceSelector peer from `k8s/llm/portkey/networkpolicy.yaml`.
- Update the comment in `k8s/llm/portkey/networkpolicy.yaml` to reflect admission from stack workloads and monitoring.
- Remove the nonexistent `ingress` namespaceSelector peer from `k8s/otel/networkpolicy.yaml`.
- Add an automated invariant test asserting that every `kubernetes.io/metadata.name` in all `namespaceSelector` blocks under `k8s/` resolves to a declared namespace in `k8s/namespaces.yaml` or a built-in namespace (`kube-system`, `default`).

## Capabilities

### New Capabilities
- `k8s-network-policies`: Namespace selector validation and isolation rules for Kubernetes network policies.

### Modified Capabilities

## Impact

- Manifest changes: `k8s/llm/portkey/networkpolicy.yaml` and `k8s/otel/networkpolicy.yaml`.
- Test suite: `tests/test_k8s_network_policies.py` gains invariant coverage for namespace references in network policies.
- No runtime impact on cluster traffic because the removed peers did not match any running pods.

## Feasibility

We confirmed the premise by inspecting cluster manifest files and verifying against live namespace inventory:
- `k8s/namespaces.yaml` declares namespaces `argocd`, `monitoring`, `otel`, `llm`, `logging`, `cloudflared`, `devops`, `agents`, `argo-workflows`, and `gitea`.
- Neither `devops-cli` nor `ingress` exists as a declared namespace.
- Live inspection confirmed that Traefik runs in `kube-system` and stack workloads run in `devops` or `llm`.
- Upstream Kubernetes documentation confirms that `namespaceSelector` matches labels on `Namespace` resources; references to nonexistent namespaces match zero pods.

## Existing Tool Considered

We considered `kubeconform` and standard Kubernetes JSON schema validation.
Schema validation verifies resource syntax, but it does not validate cross-resource references such as namespace names in selectors.
We also considered writing a custom Open Policy Agent (OPA) Gatekeeper or Kyverno policy.
Adding an external admission controller policy requires running an admission webhook engine during CI, whereas an offline pytest invariant verifies the manifests with zero extra dependencies and sub-second execution.
Therefore, a focused offline pytest invariant in `tests/test_k8s_network_policies.py` satisfies the invariant check requirement with no added runtime complexity.

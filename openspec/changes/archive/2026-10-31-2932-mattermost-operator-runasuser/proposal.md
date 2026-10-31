# Proposal

## Why

Issue #2932 addresses a failure in the `mattermost-operator` deployment.
The pod `mattermost-operator` fails to start with this kubelet error:
`Error: container has runAsNonRoot and image has non-numeric user (nonroot), cannot verify user is non-root`.
The container image sets the unprivileged user by name (`nonroot`) without numeric user metadata.
The kubelet cannot confirm that the user is non-root without an explicit numeric user identifier.

## What Changes

- Add `runAsUser: 65532` and `runAsGroup: 65532` to `podSecurityContext` in `k8s/mattermost/mattermost-operator-values.yaml`.
- Add test assertions in `tests/invariants/test_k8s_argocd_apps.py` ensuring that `mattermost-operator` values configure these numeric user identifiers.

## Capabilities

### New Capabilities

- `mattermost-operator-security-context`: The `mattermost-operator` Helm values configure numeric user identifiers for non-root execution.

### Modified Capabilities

None.

## Impact

- Manifests: `k8s/mattermost/mattermost-operator-values.yaml`.
- Tests: `tests/invariants/test_k8s_argocd_apps.py`.
- Fits in one pull request.

## Feasibility

Confirmed against the real system:
- `kubectl describe pod -n mattermost-operator` reports:
  `Error: container has runAsNonRoot and image has non-numeric user (nonroot), cannot verify user is non-root`.
- The Helm chart template passes `podSecurityContext` directly to `spec.template.spec.securityContext`.
- Distroless container images define the `nonroot` user as UID 65532 and GID 65532.
- Explicit numeric identifiers satisfy the Kubernetes `runAsNonRoot` validation in kubelet.

## Existing Tool Considered

Helm chart `podSecurityContext` configuration. The Helm chart exposes `podSecurityContext` to configure pod security parameters. Adding numeric user identifiers uses this standard mechanism without modifying upstream chart templates.

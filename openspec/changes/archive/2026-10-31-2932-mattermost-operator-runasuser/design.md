# Design

## Context

See proposal.md - Why.
The Helm chart `mattermost-operator` renders the deployment for the operator.
The values file `k8s/mattermost/mattermost-operator-values.yaml` configures `runAsNonRoot: true`.
Because the image `mattermost/mattermost-operator:v1.25.4` specifies a non-numeric user (`nonroot`), the kubelet refuses to start the container.

## Goals / Non-Goals

**Goals:**
- Configure numeric user and group identifiers (`65532`) for `mattermost-operator`.
- Add an invariant test ensuring that the values file specifies these numeric identifiers.

**Non-Goals:**
- Modifying the upstream Mattermost Operator container image.
- Changing permissions or resources for other workloads.

## Decisions

### D1: Set numeric UID and GID in `podSecurityContext`
- **Choice**: Add `runAsUser: 65532` and `runAsGroup: 65532` under `podSecurityContext` in `k8s/mattermost/mattermost-operator-values.yaml`.
- **Rationale**: The official Mattermost Operator image builds on distroless and assigns UID 65532 to `nonroot`. Kubelet verifies UID 65532 directly and satisfies `runAsNonRoot: true`.
- **Alternative considered**: Removing `runAsNonRoot: true`.
  - *Evidence rejecting alternative*: Removing non-root enforcement violates the project security baseline defined in `SECURITY.md`.

### D2: Assert numeric identifiers in invariant tests
- **Choice**: Add a test in `tests/invariants/test_k8s_argocd_apps.py` that verifies `mattermost-operator-values.yaml` defines `runAsUser == 65532` and `runAsGroup == 65532`.
- **Rationale**: Invariant tests gate CI and prevent regressions in security context settings.

## Risks / Trade-offs

- [Explicit UID coupling] → Low risk. The UID 65532 matches the standard nonroot UID in distroless and minimal container images.

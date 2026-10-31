# Design

## Context

See proposal.md - Why.
The manifest `k8s/mattermost/mattermost.yaml` configures the Mattermost Custom Resource managed by the Mattermost Operator.
The namespace `mattermost` enforces the `restricted` Pod Security Standard.
Kubernetes restricted security requires all containers to set `allowPrivilegeEscalation: false` and drop all capabilities.

## Goals / Non-Goals

**Goals:**
- Configure `allowPrivilegeEscalation: false` and `capabilities.drop: ["ALL"]` in `k8s/mattermost/mattermost.yaml`.
- Add an invariant test ensuring that the manifest specifies these container security parameters.

**Non-Goals:**
- Relaxing the `restricted` Pod Security Standard on the `mattermost` namespace.
- Altering database or operator security settings.

## Decisions

### D1: Specify `containerSecurityContext` in `spec.podTemplate`
- **Choice**: Add `containerSecurityContext` with `allowPrivilegeEscalation: false` and `capabilities.drop: ["ALL"]` under `spec.podTemplate` in `k8s/mattermost/mattermost.yaml`.
- **Rationale**: The Mattermost Operator forwards `podTemplate.containerSecurityContext` to the Mattermost app server container security context. This satisfies the restricted Pod Security Standard.
- **Alternative considered**: Lowering the namespace policy to `baseline`.
  - *Evidence rejecting alternative*: Violates project security requirements in `SECURITY.md` and fails invariant test `test_mattermost_namespaces_in_namespaces_yaml`.

### D2: Assert container security context in invariant tests
- **Choice**: Add a test in `tests/invariants/test_k8s_argocd_apps.py` that inspects `k8s/mattermost/mattermost.yaml` and verifies `podTemplate.containerSecurityContext`.
- **Rationale**: Invariant tests gate CI and prevent regressions in security context manifests.

## Risks / Trade-offs

- [Compatibility with plugins] → None. Local plugins run within allowed unprivileged execution boundaries.

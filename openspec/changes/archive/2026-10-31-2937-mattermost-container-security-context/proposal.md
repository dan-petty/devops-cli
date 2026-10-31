# Proposal

## Why

Issue #2937 addresses a Pod Security admission failure for the Mattermost application workload.
The namespace `mattermost` enforces the `restricted` Pod Security standard.
The manifest `k8s/mattermost/mattermost.yaml` defines `podTemplate.securityContext` but omits `podTemplate.containerSecurityContext`.
The ReplicaSet controller fails to create the Mattermost pod because the container lacks `allowPrivilegeEscalation: false` and `capabilities.drop: ["ALL"]`.

## What Changes

- Add `containerSecurityContext` with `allowPrivilegeEscalation: false` and `capabilities.drop: ["ALL"]` under `spec.podTemplate` in `k8s/mattermost/mattermost.yaml`.
- Add test assertions in `tests/invariants/test_k8s_argocd_apps.py` ensuring that `mattermost.yaml` specifies these container security settings.

## Capabilities

### New Capabilities

- `mattermost-app-security-context`: The Mattermost Custom Resource defines container security parameters conforming to the restricted Pod Security standard.

### Modified Capabilities

None.

## Impact

- Manifests: `k8s/mattermost/mattermost.yaml`.
- Tests: `tests/invariants/test_k8s_argocd_apps.py`.
- Fits in one pull request.

## Feasibility

Confirmed against the real system:
- The ReplicaSet controller emitted:
  `Error creating: pods "mattermost-578c98b7c7-lbts5" is forbidden: violates PodSecurity "restricted:latest": allowPrivilegeEscalation != false (container "mattermost" must set securityContext.allowPrivilegeEscalation=false), unrestricted capabilities (container "mattermost" must set securityContext.capabilities.drop=["ALL"])`.
- The Mattermost Operator CRD supports `spec.podTemplate.containerSecurityContext`.
- Patching `containerSecurityContext` onto the Mattermost CR allowed the pod to be admitted, scheduled, and start successfully.

## Existing Tool Considered

Mattermost Operator CRD `containerSecurityContext` configuration. The CRD provides `podTemplate.containerSecurityContext` specifically for container-level security parameters. Using this built-in field configures the deployment without custom patches or overlays.

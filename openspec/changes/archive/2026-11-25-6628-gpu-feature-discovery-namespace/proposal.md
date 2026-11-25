# Proposal: #6628

## Why
`k8s/gpu-feature-discovery/daemonset.yaml` deploys the `gpu-feature-discovery` DaemonSet into `default`, and `k8s/argocd/apps/gpu-feature-discovery.yaml` targets `default`. `k8s/namespaces.yaml` does not define `default`, so the workload receives no stack Pod Security Admission labels and stays outside the `k8s/namespaces.yaml` namespaces (`DEFAULT_ROADMAP_PROJECT_REVIEW_NAMESPACES`).

## What Changes
- Define Namespace `gpu-feature-discovery` in `k8s/namespaces.yaml` with `app.kubernetes.io/part-of: devops-cli-stack`, `privileged` Pod Security labels (`enforce`, `warn`, `audit`), and `argocd.argoproj.io/sync-options: Prune=false,Delete=false`.
- Set `metadata.namespace: gpu-feature-discovery` on `k8s/gpu-feature-discovery/daemonset.yaml` and update `ignore-check.kube-linter.io/non-isolated-pod` to reference namespace `gpu-feature-discovery`.
- Set `spec.destination.namespace: gpu-feature-discovery` on `k8s/argocd/apps/gpu-feature-discovery.yaml`.
- Admit `namespace: gpu-feature-discovery` in AppProject `homelab-system` (`k8s/argocd/apps/projects.yaml`) while keeping `default`.
- Add `"gpu-feature-discovery"` to `DEFAULT_ROADMAP_PROJECT_REVIEW_NAMESPACES` (`src/devops_cli/config/defaults.py`) so project review defaults match `k8s/namespaces.yaml`.
- Add manifest and config tests in `tests/k8s/test_k8s_gpu_feature_discovery.py` and `tests/config/test_project_review_namespaces_setting.py`.

## Capabilities
- Modified: `homelab-project-destinations`

## Impact
- `k8s/namespaces.yaml`
- `k8s/gpu-feature-discovery/daemonset.yaml`
- `k8s/argocd/apps/gpu-feature-discovery.yaml`
- `k8s/argocd/apps/projects.yaml`
- `src/devops_cli/config/defaults.py`
- `openspec/specs/homelab-project-destinations/spec.md`
- `tests/k8s/test_k8s_gpu_feature_discovery.py`
- `tests/config/test_project_review_namespaces_setting.py`

Fits in one pull request.

## Feasibility
Confirmed on `origin/main`:
- `k8s/gpu-feature-discovery/daemonset.yaml:5,16` sets `namespace: default` and cites `default` in `ignore-check.kube-linter.io/non-isolated-pod`.
- `k8s/argocd/apps/gpu-feature-discovery.yaml:11,18` sets `project: homelab-system` and `destination.namespace: default`.
- `k8s/argocd/apps/projects.yaml:162-216` defines `homelab-system` destinations.
- `k8s/namespaces.yaml` has no `gpu-feature-discovery` entry, and `src/devops_cli/config/defaults.py:948-964` lists the 15 committed namespaces without `gpu-feature-discovery`.

## Existing Tool Considered
No external tool moves a workload DaemonSet out of `default` across bespoke Kustomize, Argo CD AppProject, and Pod Security Admission manifests (`alternatives.verdict: none`). The change edits static manifests and one tuple element, costing negligible review time with no custom runtime machinery to maintain.

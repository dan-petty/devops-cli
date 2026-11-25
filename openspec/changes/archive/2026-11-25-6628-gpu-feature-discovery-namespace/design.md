# Design

## Decisions
- Name the dedicated namespace `gpu-feature-discovery` to match `k8s/gpu-feature-discovery/`, the `DaemonSet`, and the Argo CD `Application`.
- Set `pod-security.kubernetes.io/{enforce,warn,audit}: privileged` on Namespace `gpu-feature-discovery` alongside `app.kubernetes.io/part-of: devops-cli-stack` and `argocd.argoproj.io/sync-options: Prune=false,Delete=false`, because the DaemonSet runs privileged containers with host `/sys` mounts (`#5646`).
- Keep `default` in `homelab-system`'s `spec.destinations` when adding `gpu-feature-discovery` so other resources targeting `default` are not broken.
- Retain `ignore-check.kube-linter.io/non-isolated-pod` on `daemonset.yaml` and update its reason text to name `gpu-feature-discovery` (`#6109` adds its NetworkPolicy separately).
- Add `"gpu-feature-discovery"` to `DEFAULT_ROADMAP_PROJECT_REVIEW_NAMESPACES` (`src/devops_cli/config/defaults.py`) so default review namespace scoping includes the new namespace without overriding configuration.

## Rejected alternatives
- Use `baseline` or `restricted` Pod Security Admission labels: rejected because privileged NVML/sysfs containers would be rejected by the API server.
- Remove `default` from `homelab-system` destinations or drop the `non-isolated-pod` ignore annotation: rejected because other workloads may target `default` and `#6109` has not added a NetworkPolicy yet.

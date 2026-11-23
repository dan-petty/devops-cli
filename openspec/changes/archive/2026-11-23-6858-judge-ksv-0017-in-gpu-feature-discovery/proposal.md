# Proposal: #6858

## Why

Trivy reports HIGH KSV-0017 on `k8s/gpu-feature-discovery/daemonset.yaml`.
The container runs with `privileged: true` to access GPU devices and host sysfs.
The non-privileged manifest is tracked in #5646.
Per SECURITY.md, an agent judges a HIGH Trivy-config finding with a time-limited ignore entry in `.trivyignore.yaml`.

## What Changes

- Update `.trivyignore.yaml` with renewed `expired_at: 2026-11-26` for `KSV-0017` on `k8s/gpu-feature-discovery/daemonset.yaml`.
- Renew companion entries for `KSV-0121` and `KSV-0118` on `k8s/gpu-feature-discovery/daemonset.yaml` to `2026-11-26`.
- Keep the statement that names the privileged GPU device and sysfs access of GFD v0.16.2 and tracking issue #5646.

## Capabilities

### Modified
- `trivy-config-alerts`: The privileged GPU workload holds a renewed dated ignore entry.

## Impact

The IaC scan ignores KSV-0017 on the GPU feature discovery DaemonSet until 2026-11-26.

## Feasibility

Confirmed against the real system: Trivy reports KSV-0017 on `k8s/gpu-feature-discovery/daemonset.yaml`.
Setting `expired_at: 2026-11-26` in `.trivyignore.yaml` allows `devops scan report --scanner trivy-config` to suppress the alert.

## Existing Tool Considered

Trivy is the open and maintained scanner for Kubernetes IaC misconfigurations.
It reads `.trivyignore.yaml` with `--ignorefile`.
No new component is built.

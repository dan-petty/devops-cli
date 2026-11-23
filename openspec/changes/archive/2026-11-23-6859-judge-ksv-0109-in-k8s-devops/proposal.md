# Proposal: #6859

## Why

Trivy reports HIGH KSV-0109 on `k8s/devops/renovate/configmap.yaml`.
The ConfigMap holds a read of the token file from the init container, not a stored secret.
Per SECURITY.md, an agent judges a HIGH Trivy-config finding with a time-limited ignore entry in `.trivyignore.yaml`.

## What Changes

- Add a `misconfigurations` entry to `.trivyignore.yaml` for rule `KSV-0109` on path `k8s/devops/renovate/configmap.yaml`.
- Set `expired_at` to `2026-11-26` (3 days from entry per the SECURITY.md agent limit).
- Give a statement that explains the token read from the init container.

## Capabilities

### Modified
- `trivy-config-alerts`: The Renovate ConfigMap holds a dated ignore entry.

## Impact

The IaC scan ignores KSV-0109 on `k8s/devops/renovate/configmap.yaml` until 2026-11-26.

## Feasibility

Confirmed against the real system: Trivy reports KSV-0109 on `k8s/devops/renovate/configmap.yaml`.
Adding the entry to `.trivyignore.yaml` suppresses the finding during `devops scan report --scanner trivy-config`.

## Existing Tool Considered

Trivy is the open and maintained scanner for Kubernetes IaC misconfigurations.
It reads `.trivyignore.yaml` with `--ignorefile`.
No new component is built.

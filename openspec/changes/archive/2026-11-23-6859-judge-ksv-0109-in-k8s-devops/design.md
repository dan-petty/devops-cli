# Design

## Decisions

### Add KSV-0109 dated ignore entry for renovate configmap
The file `k8s/devops/renovate/configmap.yaml` configures self-hosted Renovate.
The JavaScript code reads the token file that the init container wrote and removes the file at once.
Trivy flags the variable name `token` as an unsafe secret in a ConfigMap.
Per SECURITY.md, an agent adds a time-limited ignore entry to `.trivyignore.yaml` with an expiry date of 3 days (`2026-11-26`).

### Keep ConfigMap unmodified
The ConfigMap does not store a secret.
Renovate needs the configuration to read the token file at startup.
Changing the token key or mechanism breaks Renovate authentication.

## Rejected alternatives

- **Set 90-day expiry directly**: Only the repository owner can approve an ignore longer than 14 days. An agent follows the 3-day renewal limit.
- **Dismiss alert 286 in GitHub**: An agent does not dismiss code scanning alerts.

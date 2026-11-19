# Design

## Decisions

### Add KSV-0014 dated ignore entry for kubernetes_adversary.yaml
The file `tests/fixtures/prompt_adversaries/kubernetes_adversary.yaml` is test input for prompt adversary defense tests. Per SECURITY.md, an agent adds a time-limited ignore entry to `.trivyignore.yaml` with an expiry date of 3 days (`2026-11-21`).

### Keep test fixture unmodified
The fixture represents an adversarial Kubernetes manifest with prompt injection text attempting to override readOnlyRootFilesystem constraints. Modifying its security context would invalidate the adversary test input.

## Rejected alternatives

- **Set 90-day expiry directly**: Only the repository owner can approve an ignore longer than 14 days. An agent follows the 3-day renewal limit.
- **Fix the fixture**: Setting readOnlyRootFilesystem to true breaks the adversarial injection test input.
- **Dismiss alert 284 in GitHub**: An agent does not dismiss code scanning alerts.

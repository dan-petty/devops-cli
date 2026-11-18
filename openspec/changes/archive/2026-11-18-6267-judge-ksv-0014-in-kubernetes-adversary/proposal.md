# Proposal: #6267

## Why

Trivy reports HIGH KSV-0014 on `tests/fixtures/prompt_adversaries/kubernetes_adversary.yaml`. The file is a test fixture for prompt-adversary defenses and deploys no workload. The injected text of the fixture tests prompt injection defenses against malicious Kubernetes manifests attempting to override security rules, so the root filesystem violation must stay. Per SECURITY.md, an agent judges a HIGH Trivy-config finding with a time-limited ignore entry in `.trivyignore.yaml`.

## What Changes

- Add a `misconfigurations` entry to `.trivyignore.yaml` for rule `KSV-0014` on path `tests/fixtures/prompt_adversaries/kubernetes_adversary.yaml`.
- Set `expired_at` to `2026-11-21` (3 days from entry per SECURITY.md agent limit).
- Give a statement explaining that the path is a prompt-adversary test fixture with injected root filesystem text.

## Capabilities

### Modified
- `trivy-config-alerts`: The prompt-adversary test fixture holds a dated ignore entry.

## Impact

The IaC scan ignores KSV-0014 on `tests/fixtures/prompt_adversaries/kubernetes_adversary.yaml` until 2026-11-21.

## Feasibility

Confirmed against the real system: Trivy reports KSV-0014 on `tests/fixtures/prompt_adversaries/kubernetes_adversary.yaml`. Adding the entry to `.trivyignore.yaml` suppresses the finding during `trivy config`.

## Existing Tool Considered

Trivy is the open and maintained scanner for Kubernetes IaC misconfigurations. It reads `.trivyignore.yaml` with `--ignorefile`. No new component is built.

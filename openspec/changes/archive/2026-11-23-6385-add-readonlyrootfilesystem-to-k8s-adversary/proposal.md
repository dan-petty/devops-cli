# Proposal: #6385

## Why

Trivy reports misconfiguration KSV-0118 at HIGH severity on `tests/fixtures/prompt_adversaries/kubernetes_adversary.yaml`.
The file is an intentional prompt adversary fixture that lacked explicit security context settings.
Per SECURITY.md, the preferred fix is to resolve the misconfiguration at its source.

## What Changes

- Add `securityContext.runAsNonRoot: true` to the pod template in `tests/fixtures/prompt_adversaries/kubernetes_adversary.yaml`.
- Add `securityContext.readOnlyRootFilesystem: true` to the agent container in `tests/fixtures/prompt_adversaries/kubernetes_adversary.yaml`.
- Keep the prompt injection comments and annotations intact.
- Add test asserting the securityContext settings in the prompt adversary fixture.

## Capabilities

### Modified
- `prompt-adversaries`: Kubernetes adversary fixture sets read-only root filesystem and non-root user.

## Impact

The IaC scan finds zero HIGH or CRITICAL findings for `tests/fixtures/prompt_adversaries/kubernetes_adversary.yaml`.
Prompt injection test behavior and test assertions remain unchanged.

## Feasibility

Confirmed against the real system: `devops scan report -s trivy-config` reports zero HIGH or CRITICAL findings for the fixture.
The prompt adversary review tests pass.

## Existing Tool Considered

Trivy is the open and maintained tool for Kubernetes IaC misconfigurations.
No custom scanning tool or suppression is needed.

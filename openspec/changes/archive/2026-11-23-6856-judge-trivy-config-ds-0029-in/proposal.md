# Proposal: #6856

## Why

Trivy reports HIGH DS-0029 on `.venv/lib/python3.14/site-packages/harbor/cli/template-adapter/task-template/environment/Dockerfile`.
The file is part of the installed Harbor package under `.venv`.
Local edits are overwritten by package installation.
Per SECURITY.md, an agent judges a HIGH Trivy-config finding with a time-limited ignore entry in `.trivyignore.yaml`.

## What Changes

- Update `.trivyignore.yaml` with renewed `expired_at: 2026-11-26` for `DS-0029` on the Harbor template Dockerfile.
- Reference tracking issue #6856 in the ignore statement.

## Capabilities

### Modified
- `trivy-config-alerts`: The Harbor task-template Dockerfile holds a renewed dated ignore entry for DS-0029.

## Impact

The IaC scan ignores DS-0029 on the Harbor template Dockerfile until 2026-11-26.

## Feasibility

Confirmed against the real system: Trivy reports DS-0029 on the Harbor template Dockerfile in `.venv`.
Setting `expired_at: 2026-11-26` in `.trivyignore.yaml` suppresses the alert during `devops scan report --scanner trivy-config`.

## Existing Tool Considered

Trivy is the open and maintained scanner for container and IaC misconfigurations.
It reads `.trivyignore.yaml` with `--ignorefile`.
No new component is built.

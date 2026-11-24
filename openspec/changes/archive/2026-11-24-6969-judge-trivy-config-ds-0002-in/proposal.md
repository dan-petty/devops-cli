# Proposal: #6969

## Why

Trivy reports `DS-0002` at `HIGH` severity on `.venv/lib/python3.14/site-packages/harbor/cli/template-task/environment/Dockerfile` (alert 1189, issue #6969).
The `harbor` Python dependency installs this template Dockerfile into the local virtual environment, and the repository does not track or build it.
Per `SECURITY.md`, an agent judges a `HIGH` `Trivy-config` alert on an external dependency file with a 3-day entry in `.trivyignore.yaml`.
The change fits one pull request.

## What Changes

- Add one `misconfigurations` entry to `.trivyignore.yaml` for rule `DS-0002` and path `.venv/lib/python3.14/site-packages/harbor/cli/template-task/environment/Dockerfile`.
- Set `statement` to name the installed Harbor template Dockerfile and tracking issue `#6969`.
- Set `expired_at` to `2026-11-27` (3 days from `2026-11-24`, the agent limit in `SECURITY.md`).
- No consumer-observable command, option, or spec requirement changes because the entry only records a temporary `trivy-config` suppression, so `skip_specs: true` applies.

## Capabilities

None. The change modifies no `src/` code and adds no consumer-facing behavior.

## Impact

- `trivy config --ignorefile .trivyignore.yaml` and `devops scan report --scanner trivy-config` suppress `DS-0002` on `.venv/lib/python3.14/site-packages/harbor/cli/template-task/environment/Dockerfile` until `2026-11-27`.

## Feasibility

Confirmed against the real system: `.venv/lib/python3.14/site-packages/harbor/cli/template-task/environment/Dockerfile` contains `FROM ubuntu:24.04` and `WORKDIR /app` with no `USER` instruction, and `trivy config` reports `DS-0002` (`HIGH`).
`src/devops_cli/security/trivy.py:241-246` passes `--ignorefile .trivyignore.yaml` during `trivy-config` scans.

## Existing Tool Considered

Trivy (`aquasecurity/trivy`) is the open, maintained scanner that reports `DS-0002` and reads `.trivyignore.yaml`.
The change adds one configuration entry and builds no custom code or replacement tool, so the build cost is zero tokens of new code.

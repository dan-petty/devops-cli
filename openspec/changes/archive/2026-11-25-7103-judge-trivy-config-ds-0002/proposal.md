# Proposal: #7103

## Why

Trivy reports `DS-0002` at `HIGH` severity on `.venv/lib/python3.14/site-packages/harbor/cli/template-task/pytest-tests/Dockerfile` (alert 1192, issue #7103). The `harbor` Python dependency installs this template Dockerfile into the local virtual environment, and the repository does not track or build it. Per `SECURITY.md`, an agent judges a `HIGH` `Trivy-config` alert on an external dependency file with a 3-day entry in `.trivyignore.yaml`. Closes #7103.

## What Changes

- Add one `misconfigurations` entry to `.trivyignore.yaml` for rule `DS-0002` and path `.venv/lib/python3.14/site-packages/harbor/cli/template-task/pytest-tests/Dockerfile`.
- Set `statement` to name the installed Harbor template-task pytest-tests Dockerfile and tracking issue `#7103`.
- Set `expired_at` to `2026-11-28` (3 days from `2026-11-25`, the agent limit in `SECURITY.md`).
- No consumer-observable command, option, or spec requirement changes (`skip_specs: true`).

## Capabilities

None. The change modifies no `src/` code and adds no consumer-facing behavior.

## Impact

- `trivy config --ignorefile .trivyignore.yaml` and `devops scan report --scanner trivy-config` suppress `DS-0002` on `.venv/lib/python3.14/site-packages/harbor/cli/template-task/pytest-tests/Dockerfile` until `2026-11-28`.

## Feasibility

Confirmed against the real workspace: `.venv/lib/python3.14/site-packages/harbor/cli/template-task/pytest-tests/Dockerfile` starts with `FROM python:3.12-slim`, `WORKDIR /app`, and `COPY . /tests/` with no `USER` instruction, and `devops scan report --scanner trivy-config` reports 1 `HIGH` finding (`DS-0002`) on that path.

## Existing Tool Considered

Trivy (`aquasecurity/trivy`) is the open, maintained scanner that reports `DS-0002` and reads `.trivyignore.yaml`. Adding one path-scoped entry builds no new code (0 tokens of code, ~2k tokens total).

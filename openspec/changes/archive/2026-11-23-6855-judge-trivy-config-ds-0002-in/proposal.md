# Proposal: #6855

## Why

Trivy reports rule DS-0002 at HIGH severity for `.venv/lib/python3.14/site-packages/harbor/cli/template-adapter/task-template/environment/Dockerfile`.
The harbor package installs this file into the local virtual environment.
The repository code does not hold this file, so the project cannot edit it directly.
The alert stays open until the repository records a judgment under SECURITY.md.

## What Changes

- Add one time-limited ignore entry for rule DS-0002 and the harbor Dockerfile path to `.trivyignore.yaml`.

## Capabilities

- `trivy-config-alerts`: add requirements for the harbor template Dockerfile DS-0002 ignore entry and expiry.

## Impact

- The `Trivy-config` scan hides the DS-0002 misconfiguration in the harbor template Dockerfile until its expiry date.

## Feasibility

- Trivy reads `.trivyignore.yaml` through `--ignorefile` when the file exists.
- Other entries in `.trivyignore.yaml` use the same format.

## Existing Tool Considered

- Trivy ignore file `.trivyignore.yaml`. No new tool is required.

# Proposal: #5947

## Why

Trivy reports rule DS-0029 at HIGH severity for `.venv/lib/python3.14/site-packages/harbor/cli/template-adapter/task-template/environment/Dockerfile`. The harbor package installs this file into the local virtualenv. The repository code does not hold this file, so the project cannot edit it directly. The alert stays open until the repository records a judgment under SECURITY.md. Closes #5947.

## What Changes

- Add one time-limited entry for rule DS-0029 and the harbor Dockerfile path to `.trivyignore.yaml`.
- Add test coverage in `tests/security/test_trivy_config_ignore.py` to verify the entry structure, path, statement, and expiry date.

## Capabilities

- `trivy-config-alerts`: add a requirement that the harbor template Dockerfile holds a dated ignore entry.

## Impact

- The `Trivy-config` scan ignores the DS-0029 misconfiguration in the virtualenv template Dockerfile until its expiry date.

## Feasibility

- Trivy reads `.trivyignore.yaml` through `--ignorefile` when the file exists.
- Other entries in `.trivyignore.yaml` use the same format.

## Existing Tool Considered

- Trivy ignore file `.trivyignore.yaml`. No new tool is required.

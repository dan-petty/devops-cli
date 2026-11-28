# Proposal: #7559

## Why

In #7559 (and earlier alerts #7558, #7393, #7392, #7276, #7275), Trivy `config` reports HIGH misconfigurations (`DS-0029`, `DS-0002`, code-scanning alerts `281` and `288`) inside `.venv/lib/python3.14/site-packages/harbor/...`, a third-party Python package directory created by `uv sync` rather than tracked repository files. Temporary `.trivyignore.yaml` suppressions expire every three days (`SECURITY.md:131`), causing `trivy-config-alerts.yml` to re-file issues repeatedly. Per `AGENTS.md` rule 11, excluding `.venv` from the `trivy config` scan fixes the root cause.

## What Changes

- Define `CONST_TRIVY_CONFIG_SKIP_DIRS` (`(".venv", "**/.venv")`) in `src/devops_cli/config/constants.py` and pass `--skip-dirs` for each entry in `TrivyConfigScanner.build_command` (`src/devops_cli/security/trivy.py`).
- Remove the four obsolete `.venv/` Harbor entries from `.trivyignore.yaml` and update `openspec/specs/trivy-config-alerts/spec.md` accordingly.
- Because `TrivyConfigScanner` arguments change and stale spec requirements are removed/added, this change carries a spec delta under `specs/trivy-config-alerts/spec.md`.

## Capabilities

### Modified Capabilities

- `trivy-config-alerts`: `TrivyConfigScanner` skips `.venv` and `**/.venv` via `--skip-dirs`, and removes the temporary Harbor `.venv/` `.trivyignore.yaml` requirements.

## Impact

- Code: `src/devops_cli/config/constants.py`, `src/devops_cli/security/trivy.py`.
- Tests: `tests/security/test_trivy_config_ignore.py`.
- Config: `.trivyignore.yaml` (removes the four `.venv/` Harbor entries).
- Fits in one pull request.

## Feasibility

- Verified `trivy config --skip-dirs .venv --skip-dirs '**/.venv' --severity HIGH,CRITICAL` skips both root `.venv/` and nested `sub/.venv/` Dockerfiles while continuing to report `app/Dockerfile`.
- Verified code-scanning alerts `281` (`DS-0029`) and `288` (`DS-0002`) both point to `.venv/lib/python3.14/site-packages/harbor/cli/template-adapter/task-template/environment/Dockerfile`.

## Existing Tool Considered

Aqua Trivy (`trivy config --skip-dirs`, already installed and wrapped by `TrivyConfigScanner` in `src/devops_cli/security/trivy.py:223-246`). Passing Trivy's native `--skip-dirs` flag uses the open tool directly; only the four `.venv/` suppression entries in `.trivyignore.yaml` are deleted.

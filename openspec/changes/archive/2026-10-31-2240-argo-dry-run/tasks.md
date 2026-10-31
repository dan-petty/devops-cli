# Tasks

## 1. Plan Builders and Dry-Run Implementation
- [x] 1.1 Add failing tests in `tests/commands/test_argo_dry_run.py` verifying dry-run output, classifications, request plans, and zero external calls for all 22 commands. Verification: `uv run pytest tests/commands/test_argo_dry_run.py -n 0`.
- [x] 1.2 Create `src/devops_cli/argo/argo_plans.py` with pure argument builders and request planners for Argo CD, Rollout, and Workflow operations. Verification: `uv run pytest tests/commands/test_argo_dry_run.py -k test_plans -n 0`.
- [x] 1.3 Wire `@dry_run_class` and request plan logic into `src/devops_cli/commands/argo.py` for `argo cd apps` commands (`bootstrap-gitops`, `list`, `status`, `sync`). Expose `--dry-run` on `sync`. Delete `@dry_run_command`. Verification: `uv run pytest tests/commands/test_argo_dry_run.py -k "cd_apps" -n 0`.
- [x] 1.4 Wire `@dry_run_class` and request plan logic into `src/devops_cli/commands/argo.py` for `fleet sync`. Delete `@dry_run_command`. Verification: `uv run pytest tests/commands/test_argo_dry_run.py -k "fleet" -n 0`.
- [x] 1.5 Wire `@dry_run_class` and request plan logic into `src/devops_cli/commands/argo.py` for `gitops` commands (`watch`, `drift`, `sync`). Wire `no-external-request` for `drift`. Delete `@dry_run_command`. Verification: `uv run pytest tests/commands/test_argo_dry_run.py -k "gitops" -n 0`.
- [x] 1.6 Wire `@dry_run_class` and request plan logic into `src/devops_cli/commands/argo.py` for `rollouts` commands (`abort`, `analyze`, `list`, `promote`, `restart`, `status`). Expose `--dry-run` on `list` and `status`. Delete `@dry_run_command`. Verification: `uv run pytest tests/commands/test_argo_dry_run.py -k "rollouts" -n 0`.
- [x] 1.7 Wire `@dry_run_class` and request plan logic into `src/devops_cli/commands/argo.py` for `argo sync`. Expose `--dry-run`. Verification: `uv run pytest tests/commands/test_argo_dry_run.py -k "argo_sync" -n 0`.
- [x] 1.8 Wire `@dry_run_class` and request plan logic into `src/devops_cli/commands/argo.py` for `workflows` commands (`list`, `logs`, `submit`). Expose `--dry-run` on all three. Verification: `uv run pytest tests/commands/test_argo_dry_run.py -k "workflows" -n 0`.
- [x] 1.9 Remove the 22 commands from `tests/fixtures/dry_run_gaps.json` and keep list sorted. Verification: `uv run pytest tests/invariants/test_dry_run_class_ratchet.py -n 0`.
- [x] 1.10 Regenerate command documentation with `uv run devops docs generate --sync-readme`. Verification: `git diff docs/ README.md`.
- [x] 1.11 Archive OpenSpec change folder with `uv run devops openspec archive 2240-argo-dry-run`. Verification: `uv run devops openspec check`.

## Workflow follow-up
Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

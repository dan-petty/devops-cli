# Tasks

## 1. Design record

Reads: `src/devops_cli/roadmap/run.py`, `src/devops_cli/roadmap/pr_conflicts.py`, `src/devops_cli/roadmap/adr.py`. Changes: `docs/adr/0021-the-roadmap-service-is-a-webhook-router-cluster-pods-run-the-roadmap-jobs-and-valkey-holds-their-shared-state.md`.

- [x] 1.1 Start only the five new rows in mode `plan`, and start `watch` in mode `on`, in rule 5 of section 8
  - Verification: `$ uv run devops ci --check --only docs`
- [x] 1.2 Add the bullet "Fix due marks" to the row `watch`, and a status paragraph
  - Verification: `$ uv run devops ci --check --only docs`

## Workflow follow-up

- #5024 builds `watch` in mode `on`. #5027 and #5028 add the fix rows in mode `plan`.
- Pending a person: review the amended rule. The merge approves it.

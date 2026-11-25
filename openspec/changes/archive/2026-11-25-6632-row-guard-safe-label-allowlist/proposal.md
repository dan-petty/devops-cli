# Proposal: #6632

## Why
The project review dispatcher's row guard (`_foreign_workload` in `src/devops_cli/roadmap/project_review/dispatch.py`) currently refuses only labels listed in `_NAMESPACE_LABELS` or `_WORKLOAD_LABELS`. Any other label holding a foreign workload or namespace (such as Argo CD's `name` or labels introduced via `label_replace` / `group_left`) passes unchecked (#6632).

## What Changes
- Replace `_WORKLOAD_LABELS` in `src/devops_cli/roadmap/project_review/dispatch.py` with a safe-label allowlist `_SAFE_ROW_LABELS` so `_foreign_workload` keeps foreign-namespace checks first, passes rows holding a project namespace label (with no foreign namespace label), skips `__name__`, and otherwise refuses any label not in `_SAFE_ROW_LABELS` (returning the sorted first unexpected label).
- Document the safe-label default refusal in `dispatch.py`, `src/devops_cli/roadmap/project_review/catalog.yaml`, and `docs/ROADMAP_WORKFLOW.md`.
- Add tests in `tests/roadmap/project_review/test_review_dispatch.py` covering unknown non-namespace labels (`name`), project-namespace rows with `name`, safe-label rows (`resource`, `le`), and all shipped `rows` facts in `catalog.yaml`.

## Capabilities

### Modified Capabilities
- `roadmap-project-review`: Switch `_foreign_workload` to default-refusal against `_SAFE_ROW_LABELS`, validate all shipped `rows` facts against the guard, and document the allowlist rule.

## Impact
- `src/devops_cli/roadmap/project_review/dispatch.py`
- `src/devops_cli/roadmap/project_review/catalog.yaml`
- `docs/ROADMAP_WORKFLOW.md`
- `tests/roadmap/project_review/test_review_dispatch.py`

## Feasibility
Confirmed against `origin/main` (`src/devops_cli/roadmap/project_review/dispatch.py:125-149, 328-344`, `src/devops_cli/roadmap/project_review/catalog.yaml`).

## Existing Tool Considered
No library validates Prometheus/Loki series labels against this repository's namespace/safe-label rules. Builds ~25 lines inside existing `_foreign_workload` in `dispatch.py`; cost ~10k tokens and under 2 hours.

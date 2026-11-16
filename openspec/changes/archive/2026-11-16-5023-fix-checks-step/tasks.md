# Tasks

## 1. Fix checks step and CLI

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/failure.py`, `src/devops_cli/roadmap/implement/implement_fix_scope.py`. Changes: `src/devops_cli/roadmap/steps/fix_checks.py` (new), `src/devops_cli/commands/roadmap_step_fix_checks.py` (new), `src/devops_cli/commands/roadmap_step.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `tests/commands/test_roadmap_step_fix_checks.py` (new), `tests/roadmap/steps/test_roadmap_step_fix_checks.py` (new).

- [x] 1.1 Write tests for fix-checks step and CLI command
  - Verification: `$ uv run pytest tests/commands/test_roadmap_step_fix_checks.py tests/roadmap/steps/test_roadmap_step_fix_checks.py`
- [x] 1.2 Implement store record keys and CLI command for fix-checks
  - Verification: `$ uv run pytest tests/commands/test_roadmap_step_fix_checks.py`
- [x] 1.3 Implement fix-checks step logic with tier 1 deterministic fixers, tier 2 model fallback, scope validation, and bounds
  - Verification: `$ uv run pytest tests/roadmap/steps/test_roadmap_step_fix_checks.py`
- [x] 1.4 Wire record keys and repair loop in implement_run.py
  - Verification: `$ uv run pytest tests/roadmap/implement/test_roadmap_implement_step_repair.py`

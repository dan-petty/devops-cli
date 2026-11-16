# Tasks

## 1. The guards of the step

Kind: behavior. Reads: `src/devops_cli/roadmap/steps/fix_plan.py`, `src/devops_cli/roadmap/status_sync.py`. Changes: `src/devops_cli/roadmap/steps/fix_checks.py`, `tests/roadmap/steps/test_roadmap_step_fix_checks.py`.

- [x] 1.1 Write failing tests: a live implement Job skips the item, and an ended Job does not; a round that ended failed, stopped or wait on the same head and check is not repeated, and a new head or check runs; a draft whose checks pass after the third repair is marked ready; a lockfile failure in a check of the class `ci_infra` goes to tier 1
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_step_fix_checks.py`
- [x] 1.2 Add the live Job guard, the guard of a repeated round, the cap of heads after the ready path, and `tier1_causes` before the infrastructure wait
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_step_fix_checks.py`

## 2. Tier 1 and the checkout

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/git_isolation.py`. Changes: `src/devops_cli/roadmap/steps/fix_checks_repair.py`, `tests/roadmap/steps/test_roadmap_step_fix_checks_repair.py`.

- [x] 2.1 Write failing tests: a lockfile failure in a test check gets `uv lock`; a docs failure in a check of the class types gets `devops docs generate`
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_step_fix_checks_repair.py`
- [x] 2.2 Start tier 1 from `tier1_causes`, and run each fixer only for its cause
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_step_fix_checks_repair.py`
- [x] 2.3 Add tests: a push whose lease breaks is refused and keeps the other writer; the checkout refuses another branch or another head and removes its worktree
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_step_fix_checks_repair.py`

## Criteria

- Group 1: The step skips a live Job and a repeated round with no model request, and marks a draft ready after the third repair.
- Group 2: Tier 1 runs the fixer of a docs or a lockfile failure in a check of any class, and the lease and the checkout guards have tests.

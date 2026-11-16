# Tasks

## 1. The cap and the task of the model fix

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_step.py`. Changes: `src/devops_cli/roadmap/implement/implement_limits.py`, `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `tests/roadmap/implement/test_roadmap_implement_limits.py`, `tests/config/test_roadmap_job_tasks.py`, `tests/config/test_unknown_config_keys.py`, `tests/security/test_config_declarations.py`, `tests/roadmap/test_roadmap_limit_classes.py`.

- [x] 1.1 Write failing tests: a `TokenCap` stops the step at its value and names its setting; `roadmap.fix_checks.token_budget` is 16,000,000; `ai.tasks.fix_checks` has its own model and a window of 128,000 tokens
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_limits.py tests/config/test_roadmap_job_tasks.py`
- [x] 1.2 Add `TokenCap` to `StepBudget`, pass it through `run_step` and `run_fix_step`, and add the two settings
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_limits.py tests/config/test_roadmap_job_tasks.py`

## 2. The step and the command

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/git/worktree_add.py`, `src/devops_cli/roadmap/implement/git_isolation.py`. Changes: `src/devops_cli/roadmap/steps/fix_checks.py`, `src/devops_cli/roadmap/steps/fix_checks_repair.py` (new), `src/devops_cli/commands/roadmap_step_fix_checks.py`, `tests/roadmap/steps/test_roadmap_step_fix_checks.py`, `tests/roadmap/steps/test_roadmap_step_fix_checks_repair.py` (new), `tests/commands/test_roadmap_step_fix_checks.py`, `src/devops_cli/lang/en/help.py`.

- [x] 2.1 Write failing tests: a run without `--confirm` writes nothing; a failed `Static Analysis` check whose log names a file of the plan ends `repaired` and pushes one commit; `--confirm` outside a runner exits 1; a repaired draft whose checks pass is marked ready
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_step_fix_checks.py tests/commands/test_roadmap_step_fix_checks.py`
- [x] 2.2 Gate every write on `confirm`, take a `Repair`, push once, and mark a repaired draft ready by `draft_readiness`
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_step_fix_checks.py`
- [x] 2.3 Build the checkout, the tier 1 fixer with its checks again, and the model fix of a runner Job, and wire them in the command
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_step_fix_checks.py tests/roadmap/steps/test_roadmap_step_fix_checks_repair.py`

## 3. Documents

Kind: docs. Reads: `docs/commands/roadmap.md`. Changes: `src/devops_cli/lang/en/help.py`, `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`, `docs/commands/roadmap.md`, `docs/adr/0021-the-roadmap-service-is-a-webhook-router-cluster-pods-run-the-roadmap-jobs-and-valkey-holds-their-shared-state.md`.

- [x] 3.1 Update the help of `--confirm` and `--source`, add the dated fact line of the cap to ADR 0021, and generate the documents
  - Verification: `$ uv run devops ci docs`

## Criteria

- Group 1: A fix step stops at `roadmap.fix_checks.token_budget` and names it.
- Group 2: The command repairs an in-scope failed check end to end, and a run without `--confirm` writes nothing.
- Group 3: The documents match the commands and the settings.

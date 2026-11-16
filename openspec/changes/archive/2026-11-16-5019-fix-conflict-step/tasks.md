# Tasks: #5019 Fix-Conflict Step

## 1. Configuration, Record Keys & Failure Mapping
- [x] 1.1 Add `FixConflictRecordKey` in `src/devops_cli/roadmap/stores/store.py` (`fix_conflict.key`, `.rounds`, `.files`, `.result`).
- [x] 1.2 Add `RoadmapFixConflictConfig` in `src/devops_cli/config/settings.py` and defaults in `defaults.py` (tier 1 mode `on`, tier 2 mode `plan`).
- [x] 1.3 Update `ACTION_BY_CLASS[FailureClass.CONFLICT]` to `FailureAction.REPAIR` in `src/devops_cli/roadmap/failure.py`.
- [x] 1.4 Update `docs/ROADMAP_WORKFLOW.md` to reflect `repair` default action and fix-conflict step behavior.

## 2. Step Implementation & CLI Command
- [x] 2.1 Implement `src/devops_cli/roadmap/steps/fix_conflict.py` with admission guards, caps, Tier 1 resolution (archive, generated docs, lockfile), Tier 2 fallback, and validation.
- [x] 2.2 Implement CLI command `fix_conflict_cmd` in `src/devops_cli/commands/roadmap_step_fix_conflict.py`.
- [x] 2.3 Register `fix-conflict` command in `src/devops_cli/commands/roadmap_step.py`.

## 3. Runner Job Integration
- [x] 3.1 Call `fix_conflict` during rebase conflicts in `src/devops_cli/roadmap/implement/implement_run.py`.
- [x] 3.2 Ensure stopped state records fix round count when conflicts cannot be resolved.

## 4. Tests & Verification
- [x] 4.1 Add unit tests for `fix_conflict` step covering archive resolution, release paths, admission/bounds, caps, and dry-run.
- [x] 4.2 Update implement job tests to verify fix round execution on rebase conflict.
- [x] 4.3 Run `devops ci` quality gates and update docs if needed.

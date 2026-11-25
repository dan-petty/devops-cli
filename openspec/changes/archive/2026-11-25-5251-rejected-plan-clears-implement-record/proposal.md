# Proposal: #5251

## Why
When a person closes a plan pull request without merging after `implement` has run on an item, the item keeps `implement.job`, `implement.stopped`, `implement.failure`, `implement.branch`, and `implement.pr` in its job record. Neither `stage._reject_plan` nor `devops roadmap return` clears those implement run keys, and `stage_ready` and `fix_plan` check `implement.job` directly instead of `job_holds`, so the stale keys hide new drafts, route `implement` back to the closed pull request, and keep `sync_statuses` deriving `Blocked`.

## What Changes
- Add shared helper `src/devops_cli/roadmap/implement/record_clear.py` defining `DELIVERY_CLEAR_KEYS`, `RUN_CLEAR_KEYS`, and `run_clear_marks()`.
- Clear `run_clear_marks()` in `stage._reject_plan` (`src/devops_cli/roadmap/stage/stage.py`) and by default in `apply_return` (`src/devops_cli/roadmap/return_item.py`), while keeping `implement.job` intact when `implement_report.return_to_new` (`src/devops_cli/roadmap/implement/implement_report.py`) calls `apply_return(..., clear_implement=False)` inside an active runner Job.
- Reuse `DELIVERY_CLEAR_KEYS` in `implement_report.py` and `src/devops_cli/roadmap/steps/review.py`.
- Update `stage_ready._recorded_pull` (`src/devops_cli/roadmap/stage/stage_ready.py`) and `fix_plan._record_reason` (`src/devops_cli/roadmap/steps/fix_plan.py`) to call `job_holds(item)` from `src/devops_cli/roadmap/status_sync.py`.
- Add regression tests in `tests/roadmap/stage/test_roadmap_stage_rejected.py`, `tests/roadmap/test_roadmap_return.py`, `tests/roadmap/stage/test_roadmap_stage_ready.py`, and `tests/roadmap/steps/test_roadmap_fix_plan.py`.

## Capabilities
- `roadmap-stage/returns`: clear implement run keys on rejected plans so `sync_statuses` and `recorded_branch` route to the new plan.
- `roadmap-return`: clear implement run keys on manual return to `New`.
- `roadmap-stage/ready`: check `job_holds` instead of raw `implement.job`.
- `roadmap-stage/fix-plan`: check `job_holds` instead of raw `implement.job`.

## Impact
- Prevents rejected plans and returned items from remaining stuck behind stale `implement.*` keys from an abandoned plan pull request.

## Feasibility
Confirmed against `origin/main` in `src/devops_cli/roadmap/stage/stage.py:4222-4254`, `src/devops_cli/roadmap/return_item.py:67-76`, `src/devops_cli/roadmap/stage/stage_ready.py:99-107`, `src/devops_cli/roadmap/steps/fix_plan.py:546-566`, and `src/devops_cli/roadmap/implement/implement_report.py:386-410`.

## Existing Tool Considered
Reuses `job_holds` in `src/devops_cli/roadmap/status_sync.py` and extends the existing delivery-key clear lists in `implement_report.py` and `review.py`; no external tool manages `ImplementRecordKey` state. Estimated cost to keep and maintain: about 5k tokens and under 1 hour.

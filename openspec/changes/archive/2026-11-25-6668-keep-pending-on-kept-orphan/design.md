# Design

## Decisions
- **Preserve `stage.pending` only for kept Ready orphans (`_remove_staged`):** Compute `kept_orphan = not removal.gone and removal.orphan and removal.item.status == CONST_ROADMAP_STATUS_READY`. Skip deleting `removal.branch` when `kept_orphan` is `True`, and exclude `StageRecordKey.PENDING` from the cleared keys passed to `store.set_marks(...)`. Deleted branches, gone branches, closed items, and non-`Ready` orphans keep clearing all keys in `STAGE_REMOVAL_KEYS`.
- **Keep `STAGE_REMOVAL_KEYS` unchanged:** `STAGE_REMOVAL_KEYS` is shared with `roadmap/steps/review.py` (`verdict/discard-plan` return-to-New clears all plan keys including `stage.pending`). Keeping `STAGE_REMOVAL_KEYS` intact preserves full plan cleanup on plan discard and branch deletion.
- **Clear `stage.pending` in `_stop_on_budget`:** Add `StageRecordKey.PENDING: None` to the mark dict written in `_stop_on_budget` (`src/devops_cli/roadmap/stage/stage.py`), matching `StagePublish._budget_stop` (`src/devops_cli/roadmap/stage/stage_job_phases.py:1040`).

## Rejected alternatives
- Removing `StageRecordKey.PENDING` from `STAGE_REMOVAL_KEYS` globally would leave stale `stage.pending` marks on deleted orphans, gone branches, closed items, and discarded plans.
- Retaining all keys in `_remove_staged` for kept orphans would retain stale plan keys (`stage.pr`, `stage.branch`, `stage.sha`, etc.).

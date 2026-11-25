# Proposal: #6668

## Why
`_remove_staged` keeps an App-only orphan branch on `origin` when the item status is `Ready`, but it still sets every key in `STAGE_REMOVAL_KEYS` to `None`, including `stage.pending`. Because `_resumable_branches` resumes a branch only while `stage.pending` is set, the next stage round sees a pushed branch with no `stage.pending` mark and leaves the item out as `held by a pushed branch`. Meanwhile, `_stop_on_budget` does not clear `stage.pending`, unlike `stage_job_phases.py` (`self.store.set_marks(held, {StageRecordKey.PENDING: None})`).

## What Changes
- Keep `stage.pending` in `_remove_staged` (`src/devops_cli/roadmap/stage/stage.py`) when the cleanup keeps an App-only branch of an open `Ready` orphan (`not removal.gone and removal.orphan and removal.item.status == CONST_ROADMAP_STATUS_READY`), while still clearing all other keys in `STAGE_REMOVAL_KEYS`.
- Continue clearing `stage.pending` when `_remove_staged` deletes the branch, clears a gone orphan, or clears a closed/non-Ready item.
- Clear `stage.pending` (`None`) in `_stop_on_budget` (`src/devops_cli/roadmap/stage/stage.py`) so a budget stop stands and a later round does not resume it as an orphan.
- Update `docs/roadmap/stage.md`, `openspec/specs/roadmap-stage/scaffold/spec.md`, `openspec/specs/roadmap-stage/job/spec.md`, and the real-git stage orphan and submit tests.

## Capabilities
- `roadmap-stage/scaffold` — keep `stage.pending` when orphan cleanup keeps a `Ready` App-only branch, clear it when deleting a branch or stopping on budget, and resume on the kept branch in the next round.
- `roadmap-stage/job` — clarify pre-create orphan cleanup behavior when an App-only branch of a `Ready` item is kept.

## Impact
- Ready items whose stage orphan cleanup kept an App-only branch now retain `stage.pending` and resume cleanly in the next stage round instead of staying stuck as held by a pushed branch until manual branch deletion.
- Items that stop on the token budget via `_stop_on_budget` clear `stage.pending` consistently with `--phase publish`.

## Feasibility
Confirmed against `origin/main` (`eb115217e`):
- `src/devops_cli/roadmap/stores/store.py:327-329`: `STAGE_REMOVAL_KEYS` includes `StageRecordKey.PENDING` (line `288`).
- `src/devops_cli/roadmap/stage/stage.py:4204-4209`: `_remove_staged` skips `git push origin --delete` when `removal.orphan and removal.item.status == CONST_ROADMAP_STATUS_READY`, yet clears `dict.fromkeys(STAGE_REMOVAL_KEYS)`.
- `src/devops_cli/roadmap/stage/stage.py:3249-3250`: `_resumable_branches` returns early unless `item.job_record.get(StageRecordKey.PENDING)` is truthy.
- `src/devops_cli/roadmap/stage/stage.py:4167-4182`: `_stop_on_budget` sets budget and question keys without clearing `StageRecordKey.PENDING` (whereas `src/devops_cli/roadmap/stage/stage_job_phases.py:1040` already clears it).
- `tests/roadmap/stage/test_roadmap_stage_scaffold.py:101`: currently asserts `not found.job_record.get(StageRecordKey.PENDING)` after `_stage_round` orphan cleanup keeps `BRANCH`, and `tests/roadmap/stage/test_roadmap_stage_submit.py:526,615` assert `"stage.pending" not in record`.
- Note on `#6521`: `#6668` has `Dependencies: None` and no hold line in its body.

## Existing Tool Considered
No open external tool manages this repository's GitHub issue job-record state (`stage.pending` / `STAGE_REMOVAL_KEYS`); the change is an internal two-line state-key fix in `src/devops_cli/roadmap/stage/stage.py` (`~15k` tokens, `< 1` day).

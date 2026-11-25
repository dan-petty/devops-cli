# Tasks

## 1. Keep pending mark on kept Ready orphans and clear on budget stop
Kind: behavior

- [x] 1.1 Add failing real-git `stage_repo` tests in `tests/roadmap/stage/test_roadmap_stage_scaffold.py` and update `tests/roadmap/stage/test_roadmap_stage_submit.py` covering kept `stage.pending` on a kept `Ready` App-only branch, clearing on deleted/gone orphans, clearing `stage.pending` on `_stop_on_budget`, and next-round resume on the kept branch.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_scaffold.py tests/roadmap/stage/test_roadmap_stage_submit.py`
- [x] 1.2 Preserve `StageRecordKey.PENDING` in `_remove_staged` when keeping an App-only branch of an open `Ready` orphan, and clear `StageRecordKey.PENDING` in `_stop_on_budget` (`src/devops_cli/roadmap/stage/stage.py`).
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_scaffold.py tests/roadmap/stage/test_roadmap_stage_orphan.py tests/roadmap/stage/test_roadmap_stage_submit.py tests/roadmap/stage/test_roadmap_stage_job_entry.py`

## 2. Update workflow documentation and check docs
Kind: other

- [x] 2.1 Update `docs/roadmap/stage.md` to state that orphan cleanup for a `Ready` item keeps `stage.pending` and clears the rest of the removal keys when it keeps the App-only branch.
  - Verification: `$ uv run devops ci --check --only docs,openspec`

## Workflow follow-up
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

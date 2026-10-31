# Tasks

## 1. The reasons and the one walk

- [x] 1.1 Write failing tests in `tests/roadmap/test_roadmap_stage_selection.py` and `tests/roadmap/test_roadmap_implement_selection.py` for `StageFilter.mismatch` (the family, the values of the filter and the value of the item), for `walk_named` (taken, left out, and beyond the limit, with and without a probe), and for the shared texts of "not an item" and "closed"
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_selection.py tests/roadmap/test_roadmap_implement_selection.py`
- [x] 1.2 Add `StageFilter.mismatch`, `walk_named` and `read_stage_selection` to `src/devops_cli/roadmap/stage.py`; use the walk in `select_stageable` and `plan_implement`; replace the four copies of the texts with `item_left_not_item` and `item_left_closed`; add `item_left_filter` and `item_left_limit`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_selection.py tests/roadmap/test_roadmap_implement_selection.py tests/roadmap/test_roadmap_stage_job.py tests/roadmap/test_roadmap_implement_job.py`

## 2. The plans list the items that matched no filter

- [x] 2.1 Write failing tests in `tests/roadmap/test_roadmap_stage_command.py` and `tests/roadmap/test_roadmap_implement_command.py` for the scenarios of "The plan lists the items that matched no filter when asked": with `--why`, without it, and the metric of skipped items
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_command.py tests/roadmap/test_roadmap_implement_command.py`
- [x] 2.2 Add `unmatched` to `StagePlan` and `ImplementPlan`, `why` to `plan_stage` and `plan_implement`, the section "Matched no filter" to both renderers, and `--why` to both commands
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_command.py tests/roadmap/test_roadmap_implement_command.py tests/roadmap/test_roadmap_stage_plan.py`

## 3. The command explain

- [x] 3.1 Write failing tests in `tests/roadmap/test_roadmap_explain.py` and `tests/roadmap/test_roadmap_explain_command.py` for the scenarios of "The command names the first rule that stops each job", "The command makes no model call and no write", "The dry run lists the reads" and "The options replace the filter and the limit for one run": an item of medium effort, a claimed item, a stopped item, an unplanned item, a recorded split, a closed issue, a missing issue, the limit, an item that is taken, a model that fails the test, a store that records writes, and the dry run with refused processes and sockets
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_explain.py tests/roadmap/test_roadmap_explain_command.py`
- [x] 3.2 Write `src/devops_cli/roadmap/explain.py` and `explain_requests` in `src/devops_cli/roadmap/request_plan.py`; add `devops roadmap explain` with the class `request-plan`, its help and its messages
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_explain.py tests/roadmap/test_roadmap_explain_command.py tests/invariants/test_dry_run_class_ratchet.py`

## 4. The documents and the archive

- [x] 4.1 Regenerate the command documents
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`
- [ ] 4.2 Archive the change
  - Verification: `uv run devops openspec archive 2911-roadmap-explain`

## Workflow follow-up

- The ledger of failed rounds holds no item. Showing a suspended job per item needs a store of the Service that a workstation can read. W10 (stuck-item metrics) is the place for it.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

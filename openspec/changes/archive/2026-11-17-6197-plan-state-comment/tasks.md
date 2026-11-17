# Tasks

## 1. The edit of a comment and its time

Kind: behavior. Changes: `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stores/github_store.py`, `src/devops_cli/roadmap/steps/comment.py`, `src/devops_cli/roadmap/item_comments.py`, `src/devops_cli/config/constants.py`, `tests/support/fakes/roadmap_store.py`.

- [x] 1.1 Add the failing tests: the GitHub store reads `updated_at` and edits a comment by its id, the store path of the upsert edits the marked comment by its id, a state comment reads as made at its last edit, and the index label skips the hidden lines
  - Verification: `$ uv run devops ci test tests/roadmap/stores/test_roadmap_github_store_comments.py tests/roadmap/stores/test_roadmap_github_store_issue_writes.py tests/roadmap/steps/test_roadmap_step_comment.py tests/roadmap/test_roadmap_item_comments.py`
- [x] 1.2 Add `IssueComment.updated_at`, `RoadmapStore.edit_comment` in both stores, the edit through the store in `steps/comment.py`, and the order and the label in `held_comments`
  - Verification: `$ uv run devops ci test tests/roadmap/stores tests/roadmap/steps/test_roadmap_step_comment.py tests/roadmap/test_roadmap_item_comments.py`

## 2. The plan-state comment of the stage job

Kind: behavior. Changes: `src/devops_cli/roadmap/stage/plan_state.py` (new), `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/lang/en/messages.py`, `tests/fixtures/roadmap_eval/stage/*/issue.txt`.

- [x] 2.1 Add the failing tests: a staged item gets a state comment and a comment of the run and no `stage.groups`, a restage edits the state comment, the open findings are in the state comment, the dry run lists the edit, and an edited state comment hides no filler return
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_apply.py tests/roadmap/stage/test_roadmap_stage_restage.py tests/roadmap/stage/test_roadmap_stage_verification.py tests/roadmap/test_roadmap_dry_runs.py tests/roadmap/test_roadmap_repair.py`
- [x] 2.2 Write the state comment with `post`, post the comment of the run, remove `StageRecordKey.GROUPS` and its writers, remove the key from the eval fixtures, and list the writes in the dry run
  - Verification: `$ uv run devops ci test tests/roadmap/stage tests/roadmap/test_roadmap_dry_runs.py tests/roadmap/test_roadmap_repair.py`

## 3. The plan-state comment of the step fix-plan

Kind: behavior. Changes: `src/devops_cli/roadmap/steps/fix_plan.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/lang/en/messages.py`, `tests/support/roadmap_fix_plan.py`.

- [x] 3.1 Add the failing tests: `plan_comment` reads the state comment by its key and skips a comment of a run in the legacy read, an attempt edits the state comment and its comment lists no open finding and no advice (a contract test: no line of text of the comment of the attempt is in the state comment), and a timeout on a legacy pull request builds the state comment from the legacy comment
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_fix_plan_comment.py tests/roadmap/steps/test_roadmap_fix_plan_budget.py`
- [x] 3.2 Read the state comment in `plan_comment`, write it in `_settle` before the comment of the attempt, take the open findings out of the comment of the attempt, and list the writes in the dry run
  - Verification: `$ uv run devops ci test tests/roadmap/steps tests/commands/test_roadmap_step_fix_plan.py tests/roadmap/stage/test_roadmap_stage_drift.py`

## 4. Documents

Kind: other. Changes: `docs/roadmap/stage.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/CLUSTER.md`.

- [x] 4.1 Describe the state comment, the comment of a run and the removed record key, and regenerate the references
  - Verification: `$ uv run devops docs generate`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

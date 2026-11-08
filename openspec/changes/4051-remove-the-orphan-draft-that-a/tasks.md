# Tasks

## 1. Remove the orphan draft by the intent mark

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_rejected.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/request_plan.py`, `tests/roadmap/stage/test_roadmap_stage_orphan.py`. Changes: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_orphan.py`.

- [ ] 1.1 In `tests/roadmap/stage/test_roadmap_stage_orphan.py`, write the tests of the criteria: `marks_write_fails`, `killed_after_push`, `retitle_between`, `foreign_commit`, `other_branch_kept`, `young_mark` and `request_count`, the guard tests (a recorded pull request, a closed item, a branch that is gone) and the dry run test. Confirm that they fail on `origin/main`
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [ ] 1.2 Add the key `PENDING = "stage.pending"` to `StageRecordKey`, and the constant `CONST_ROADMAP_STAGE_ORPHAN_AGE_SECONDS` of 3600. In `_stage_one`, write `stage.pending` with one `set_marks` before the push with the `now` of the `StageWriter`, and clear it in the marks write after the draft
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_orphan.py`
- [ ] 1.3 Add the pass `_orphans` next to `_reconcile`, call it in `plan_stage` with `now`, and add its results to `removals` and `kept`. A bad record gives no action. In `StageWriter.begin`, find the draft of an orphan removal by its head in one read of `store.open_pulls()` for the round, and close it in `_remove_staged`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_orphan.py`
- [ ] 1.4 Add the write of the mark before the push and the read of the open pull requests to `stage_requests` in `src/devops_cli/roadmap/request_plan.py`, with their texts in `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_dry_runs.py`
- [ ] 1.5 Run the tests of the stage job and the key-walk test of the example ConfigMap
  - Verification: `$ uv run devops ci test tests/roadmap/stage`

## 2. Fix the documents

Kind: other. Reads: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/stage.md`. Changes: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/stage.md`, `src/devops_cli/roadmap/stores/store.py`.

- [ ] 2.1 Add `stage.pending` to the table of keys in `docs/ROADMAP_WORKFLOW.md`, describe the orphan pass in `docs/roadmap/stage.md`, and update the docstring of `StageRecordKey`
  - Verification: `$ uv run devops ci docs`
- [ ] 2.2 Check the change and the specs
  - Verification: `$ uv run devops openspec check`

## Criteria

- Group 1: A test fails the marks write after the draft and runs the next round. It finds the draft closed, the branch deleted and the item planned again.
- Group 1: A kill between the push and the draft leaves a branch with no draft. The next round deletes the branch and clears the record.
- Group 1: A retitle between the failure and the next round changes the slug, and the mark still finds the orphan.
- Group 1: A branch with a commit of a person is kept and reported, not deleted.
- Group 1: The orphan of the job is removed, and a pushed branch of an agent for another Ready item with no mark is not touched.
- Group 1: A mark younger than the age limit is left alone.
- Group 1: A staged item adds 2 requests for the mark, a round with an orphan to remove adds 1 read of the open pull requests, and a round with a kept branch adds none.

## Workflow follow-up

- Pending a person: confirm the intent-mark approach of the proposal.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

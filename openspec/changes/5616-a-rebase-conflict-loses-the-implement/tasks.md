# Tasks

## 1. Push the unrebased head after a conflict at a wip, checkpoint or stop push

Kind: behavior. Reads: `tests/support/roadmap_implement.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`, `tests/roadmap/implement/test_roadmap_implement_checkpoint.py`, `tests/roadmap/implement/test_roadmap_implement_push_current.py`. Changes: `src/devops_cli/roadmap/implement/implement_run.py`, `tests/roadmap/implement/test_roadmap_implement_checkpoint.py`, `tests/roadmap/implement/test_roadmap_implement_push_current.py`.

- [ ] 1.1 Write the failing test `test_a_checkpoint_conflict_keeps_the_passed_group_on_the_item_branch` in `tests/roadmap/implement/test_roadmap_implement_checkpoint.py`, which moves `main` over the file of group 1 with `advance_main` after group 1 passed, then asserts at the next request that the item branch on `origin` holds the commit of group 1, that the job record holds the conflicting path, and that the run went on; rewrite `test_a_conflict_at_a_wip_push_and_at_the_stop_pushes_nothing` in `tests/roadmap/implement/test_roadmap_implement_push_current.py` as `test_a_conflict_at_a_wip_push_and_at_the_stop_keeps_the_work_on_the_item_branch`, which asserts that the item branch on `origin` holds the `wip:` commit and the commit of the stop
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_checkpoint.py tests/roadmap/implement/test_roadmap_implement_push_current.py` fails on the base
- [ ] 1.2 In `_push_passed` of `src/devops_cli/roadmap/implement/implement_run.py`, catch the `_StopError` whose `failure_class` is `FailureClass.CONFLICT`, call a new `_keep_conflict`, and return an empty note so the run goes on; a stop of another class returns the push-failed text as today. `_keep_conflict` writes `ImplementRecordKey.CONFLICT` with `json.dumps(list(stop.conflict_files))`, then pushes `self._head()` with `_push_with_lease()` when `self.origin.heads(self.branch)` is not empty and with `self.origin.push(self.branch, tip)` otherwise; it opens no pull request, and a failed push returns the push-failed text
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_checkpoint.py tests/roadmap/implement/test_roadmap_implement_push_current.py` passes

## 2. Keep the branch at an end push conflict and name the passed groups

Kind: behavior. Reads: `tests/support/roadmap_implement.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`, `tests/roadmap/implement/test_roadmap_implement_push_current.py`, `src/devops_cli/lang/en/messages.py`. Changes: `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/implement/test_roadmap_implement_push_current.py`.

- [ ] 2.1 Write the failing test `test_a_conflict_at_the_end_push_keeps_the_branch_and_names_the_passed_groups` in `tests/roadmap/implement/test_roadmap_implement_push_current.py`, which answers the archive program with a call that moves `main` over the first file of the group and then runs `archive_effect`, and asserts that the item stops, that the item branch on `origin` holds the commits of the run, and that the comment names the file, the item branch and one passed group
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_push_current.py` fails on the base
- [ ] 2.2 In `_push` of `src/devops_cli/roadmap/implement/implement_run.py`, wrap `self._sync()` in a `try` and, on a `_StopError` whose `failure_class` is `FailureClass.CONFLICT`, call `_keep_conflict` and re-raise, so the branch holds the head and the item stops with the class `conflict`. In `stop`, take the conflict note when the stop has conflict files and no push note. Add `_conflict_note`, which formats `implement_stop_kept_conflict` with the branch, `self._head()` and the count of passed groups, and `_passed_groups`, which counts the task groups whose tasks are all ticked in the archived `tasks.md` or in the active one. Add the message `implement_stop_kept_conflict` to `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_push_current.py` passes

## 3. State the conflict push and the kept branch in the documents

Kind: other. Reads: `docs/ROADMAP_WORKFLOW.md`, `docs/SDLC.md`. Changes: `docs/ROADMAP_WORKFLOW.md`, `docs/SDLC.md`.

- [ ] 3.1 Rewrite the Checkpoints paragraph of `docs/ROADMAP_WORKFLOW.md` so that a conflict at a `wip:`, checkpoint or stop push aborts the rebase and pushes the unrebased head to the item branch with a lease and no pull request, and so that a conflict at the end push keeps the branch and stops the item with the class `conflict`. Change the `implement.conflict` row of the record table to say that the checkpoint push writes it, and the stop list so that a stop after a conflict pushes the head. Rewrite the conflict sentence of `docs/SDLC.md` to name the implement Job's exception: it pushes the head after a conflict, with a lease and with the hook skipped, and it opens no pull request before the end push
  - Verification: `$ uv run devops ci docs` passes
- [ ] 3.2 Edit `docs/ROADMAP_WORKFLOW.md` and `docs/SDLC.md` to state the conflict push, the record of the conflicting paths and the conflict stop
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

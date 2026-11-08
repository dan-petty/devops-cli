# Tasks

## 1. Checkpoint each passed group and withdraw it on a return

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/implement/implement_wip.py`, `tests/support/roadmap_implement.py`, `tests/roadmap/implement/test_roadmap_implement_wip_job.py`. Changes: `tests/roadmap/implement/test_roadmap_implement_checkpoint.py` (new), `tests/support/roadmap_implement.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/implement/implement_run.py`.

- [x] 1.1 Write the failing test file `tests/roadmap/implement/test_roadmap_implement_checkpoint.py`, with the replay `test_a_runner_killed_after_two_of_four_groups_leaves_both_groups_on_origin` for a Staged and a Planned item, and cases for the second Job, the claim, the base, the withdraw (a false premise, a person who pushed, a withdraw that fails, the check of a behavior group), a failed checkpoint push and a refused draft. Add the fixture `planned_tasks` to `tests/support/roadmap_implement.py`, and amend the push count of `test_the_push_runs_in_the_worktree_with_a_lease_and_leaves_no_worktree_behind` in `tests/roadmap/implement/test_roadmap_implement_job.py`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_checkpoint.py` fails on the base
- [ ] 1.2 Add `BASE = "implement.base"` to `ImplementRecordKey` in `src/devops_cli/roadmap/stores/store.py` and to the list in its docstring. Add `implement_stop_withdraw_failed` to `RoadmapMessages` in `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_records.py`
- [ ] 1.3 In `src/devops_cli/roadmap/implement/implement_run.py`, write `implement.base` in the marks write of `_start` when the record holds none. Add `_checkpoint()`, which calls `_push_passed()` once a group passed in this run, logs a failure, and makes no more checkpoint pushes after one failure. Call it in `_groups` after `_check_premise` and before `run_step`. Add `_withdraw()` and call it at the top of `_return_to_new`. Clear `implement.base` in `_return_to_new` and in `_ready`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_checkpoint.py`
- [ ] 1.4 Amend the tests of `tests/roadmap/implement/` that read `origin` after a run, so that they hold the checkpoints of the groups that passed
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job.py tests/roadmap/implement/test_roadmap_implement_amend_job.py tests/roadmap/implement/test_roadmap_implement_wip_job.py tests/roadmap/implement/test_roadmap_implement_job_scoped.py`

## 2. State the checkpoint and the withdraw in the documents

Kind: other. Reads: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/implement.md`. Changes: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/implement.md`.

- [ ] 2.1 In `docs/ROADMAP_WORKFLOW.md`, change the claim sentence (a claim pushes nothing more), the paragraph that says that a group of one task that passed and that no push kept runs again, and the bullet "Before the push" (a checkpoint comes before the scoped checks). Add the withdraw to the list of the actions that return an item. Add a row for `implement.base` to the table of the record keys
  - Verification: `$ uv run devops ci docs`
- [ ] 2.2 In `docs/roadmap/implement.md`, change the paragraphs "The premise of a behavior group", "A plan request" and "Claims" so that they state the checkpoint and the withdraw, and add a paragraph "Checkpoints" that gives the order of one boundary
  - Verification: `$ uv run devops ci docs`

## Criteria

- Group 1: The implement job SHALL push each passed group to the item branch at the next group boundary, after the claim check and the premise check and before the step.
- Group 1: The implement job SHALL make no checkpoint push at the end boundary, and no checkpoint push before a group passed in the run.
- Group 1: A failed checkpoint push SHALL NOT stop the run, and the run SHALL make no more checkpoint pushes after it.
- Group 1: A second Job after a kill SHALL run only the groups that are not ticked, for a Staged and for a Planned item.
- Group 1: A false premise SHALL restore the tip in `implement.base` for a Staged item, and delete the branch and close the draft for a Planned item, with a lease on the tip that the job pushed.
- Group 1: A withdraw that fails SHALL stop the item as Blocked and SHALL NOT return it to New.
- Group 1: The job SHALL write `implement.base` once and clear it at ready and at a return.
- Group 2: The documents SHALL state the checkpoint, the withdraw and the order of one group boundary.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

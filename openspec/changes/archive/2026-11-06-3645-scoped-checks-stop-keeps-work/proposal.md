# Proposal

## Why

Issue #3645: a stop in the scoped checks phase of the implement job discards finished work. `_scoped_checks` sets `stop.push` to false for each stop in the phase. The commits of the finished task groups stay in the worktree of the Job, and the Job removes that worktree. The next Job starts from the staged branch and runs every group again. The stop comment does not say what the job kept, because `stop` calls `_kept_note` only when `stop.push` is true.

This is the case of #3020 and #3078: all groups are done and one check is red. A budget stop of a fix step in this phase loses the same work. #3054 keeps the work of a stopped group, but not the work of an item whose groups all passed.

## What Changes

- **Where the kept work lives: the item branch.** A stop in the scoped checks pushes the branch of the item to `origin` with the push that every other stop already uses (`_push_passed`: a push with a lease, or the publish of a Planned item with its draft). The next Job takes the branch from `origin` with `add_worktree`, as it does for a `wip:` commit. No separate ref is made.
- **The rule "the Job pushes only a head that passed" changes.** The scoped checks stay a filter before the push of a finished item. They no longer stop the push at a stop. The new rule is: the job pushes a finished item only after the scoped checks pass, and at a stop it pushes the commits that passed their own step. A pushed head that failed a scoped check is a draft, and the ready mark stays with `draft_readiness` and the checks of the pull request. Why: the required checks of the draft pull request are the gate, and no person merges a draft. The old rule lost hours of finished work and gained nothing, because a stop at any other step already pushes its commits that passed.
- `_scoped_checks` stops setting `stop.push` to false, and the error stop of the phase pushes. Every stop of the phase keeps the work: a check that fails after the last round, a fix step that stops (a budget, no change, a lost test), an error and a command that runs out of time.
- The stop comment names the kept work. `_StopError` gets the flag `kept_branch`, which the phase sets. When the stop has no `wip:` commit to name and the flag is set, `_kept_note` names the branch on `origin` and its last commit, and says that the pull request stays a draft and that the next run runs no finished group.
- The job stops before `_ready`, so a stop sends no ready request. A test holds this.
- **The selection takes a branch whose change is archived.** The plan check of the judge (`_plan_reason`, #3615) reads the change folder at the head of the branch. After the archive commit the folder is in `openspec/changes/archive/`, so the judge left the item out with "The head holds no change folder". The kept work could not be resumed. `_plan_reason` now returns no problem when the head holds the archived change of the issue and no active one: the stage gates passed the plan before the job archived it. The check reuses `planned_changes_at`.
- The spec `roadmap-implement-job` and `docs/ROADMAP_WORKFLOW.md` state the new rule. The module docstring of `implement_run.py` and the docstring of `_scoped_checks` change with it.
- The four tests that assert "pushes nothing" in this phase (a failed check, a stopped fix step, a command that runs out of time, an error) assert the kept work instead.
- The change fits one pull request. It does not fix #3273 (a stopped step opens a draft pull request): `_push_passed` and `_publish` stay as they are.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job`: the scoped checks gate the push of a finished item only; a stop in the phase pushes the commits that passed and the comment names them; the selection takes a branch whose change is archived

## Impact

- Code: `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/roadmap/implement.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/test_roadmap_implement_job_scoped.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`, `openspec/specs/roadmap-implement-job/spec.md`
- Left as they are, on purpose: `draft_readiness`. A pushed head that failed a scoped check fails or waits on its own checks, and the job reaches `_ready` only after a pass of the whole sequence.

## Dependencies

None. #3273 touches `_push_passed` and `_publish` too; this change does not edit those two functions.

## Feasibility

Checked on `origin/main` ffaea530, on 2026-11-06.

1. The defect is real. `git grep -n "push" -- src/devops_cli/roadmap/implement_run.py` shows `stop.push = False` in `_scoped_checks` and `push=False` in its error branch. `stop` calls `_push_passed` and `_kept_note` only when `stop.push` is true.
2. The tests `test_a_check_that_no_fix_repairs_stops_the_item_and_pushes_nothing` and `test_a_fix_step_that_stops_in_the_scoped_checks_pushes_nothing` assert `origin_log() == ["fix(roadmap): plan"]` and no push, so the loss is a tested behavior, not a side effect.
3. The resume path in the run needs no new code. After the archive commit, `_active_change` returns None, so `_groups` returns at once and runs no step. `_finish_change` skips the archive, and `_push` runs the scoped checks. The selection is different, and the refine proposal missed it. A test that ran a second Job after the stop found that `plan_implement(item=1)` left the item out with "The head holds no change folder `openspec/changes/1-*/`": `_Judge._plan_reason` calls `change_root`, which looks only under `openspec/changes/<issue>-`. So the premise "the next Job continues from the kept work" is false until the judge accepts an archived change. This change adds that, in one small function. The same refusal affected a retry after any stop that follows the archive.
4. The stop path is safe to push from. A stopped fix step resets the checkout to its last commit, so the push holds committed work only. `_push_passed` catches a failed push and puts it in the comment.
5. No ready request follows a stop: `execute` raises in `_push`, before `_ready`.

## Existing Tool Considered

No open, maintained tool covers the need. The change removes a flag in the job's own push path, and git, which the job already uses, pushes the commits. The change reuses `_push_passed`, `_push_with_lease`, `_publish` and `kept_commits`, and adds one flag and one message. Cost to build: about 40,000 tokens (code, tests, documents). Cost to keep: about 2,000 tokens each quarter. Elapsed time: under one day. The judge reuses `planned_changes_at`. The change deletes the branch of `_scoped_checks` that forces `push` to false and the four assertions of "pushes nothing".

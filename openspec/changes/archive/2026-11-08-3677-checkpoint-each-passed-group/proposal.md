# Proposal

## Why

The implement job records a passed group but does not push it (#3677). A `wip:` push (#3054) happens only while tasks of a group are unticked. So a group of one task has no copy on origin until the final push. An item has 4 groups of one task each. The runner is killed in group 3. Origin holds only the staged plan, or nothing for a Planned item. Groups 1 and 2 are lost, and the continuation Job (#3721) runs them again.

## What Changes

- Add `ImplementRecordKey.BASE` (`implement.base`) to `src/devops_cli/roadmap/stores/store.py`. `_start` writes it once, in its existing marks write: the sha of `origin/<branch>` for a Staged item, or `new` for a Planned item. A second Job of the same item keeps the first value. `_ready` and `_return_to_new` clear it.
- Add `_checkpoint()` to `_ItemRun` in `src/devops_cli/roadmap/implement/implement_run.py`. It calls `_push_passed()` before each group, but only after a group passed in this run. A failed push goes to the log and the run goes on. After one failed push, the run makes no more checkpoint pushes. The final push still runs.
- Call it in `_groups` after `_require_unclaimed` and `_check_premise`, and before `run_step`. The end boundary stays as it is.
- Add `_withdraw()` and call it at the top of `_return_to_new`, so the `premise` request and the behavior-group check both use it. Staged: push the sha in `implement.base` back to the branch, with a lease on the tracking tip. Planned: when `origin` holds the branch, delete it with the same lease, then close the recorded draft pull request. A git or GitHub error, or a failed lease, stops the item as Blocked and does not return it to New.
- Add one reason string for a failed withdraw to `src/devops_cli/lang/en/messages.py`.
- Spec deltas: `roadmap-implement-job` gets one new requirement and five modified ones. `roadmap-item-claim` gets one modified requirement. The change is observable by a consumer (the branch on origin, the draft pull request and the job record), so it carries deltas.
- Documents: `docs/ROADMAP_WORKFLOW.md` and `docs/roadmap/implement.md`.
- The change adds a job record key and no setting. No Settings model changes, so the rule that Settings models ignore unknown keys is not touched.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job`: The job checkpoints each passed group on the item branch, and withdraws the checkpoints when a premise returns the item.
- `roadmap-item-claim`: A claim keeps the checkpoints that an earlier boundary pushed.

## Impact

- Code: `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/implement.md`
- Tests: `tests/roadmap/implement/test_roadmap_implement_checkpoint.py` (new), `tests/support/roadmap_implement.py`, and the tests of `tests/roadmap/implement/` that read `origin` after a run

## Feasibility

Checked on 2026-11-08 at origin/main c8990bed.

- No merged change, open pull request or newer issue does this work. A search of `src/devops_cli/roadmap/implement/` and `src/devops_cli/roadmap/stores/store.py` finds no `_checkpoint`, `_withdraw` or `implement.base`. The open pull requests #4174, #4175 and #4176 do not touch `implement_run.py`. The blocker #3645 is closed (completed, pull request #3818 merged), so the text of the scoped-stop scenarios is on main. #4070 and #4071 are open and wait on this change.
- The premise holds in the code. `_groups` ends each group with `self._record(group=..., sha=...)`, and `_record` only calls `store.set_marks`. `_keep` pushes only while tasks of a group are unticked. `_push_passed` already does the Staged lease push or the Planned `_publish`, and it returns a failure text instead of raising. `_return_to_new` has two callers, `_return_premise` and `_check_premise`, so one `_withdraw` there covers both returns. `_start` has one `set_field(..., marks=marks)` write.
- The lease restore works. On a local bare origin, `git push --force-with-lease=<branch>:<tracking tip> origin <base>:refs/heads/<branch>` restored the base when the job pushed last, and Git refused it with `stale info` when a person pushed after the job. `git ls-remote --heads origin <branch>` returns no line for a missing branch.
- The lease also works on a delete. With git 2.55.0, `git push --force-with-lease=<branch>:<tracking tip> origin --delete <branch>` deleted the branch when the job pushed last and was refused with `stale info` when a person pushed after the job. So a Planned withdraw keeps the push of a person, as a Staged withdraw does.
- A first run of the new tests on a scratch build of the change passed 25 of 25 on a clone with a real `origin` and a real `git`. The same tests fail on origin/main (see the `fail-to-pass` run in the pull request comment).
- The remote is a local bare repository in every test. A real GitHub remote was not tested. The issue says the same.
- The first checkpoint of a Planned item publishes the branch and opens the draft. A draft that GitHub refuses takes the branch off `origin` again (`_publish`), and the run makes no more checkpoint pushes.
- A checkpoint before group 1 would push only the rebase of the staged plan. It would start CI for no passed group. So `_checkpoint` waits until a group passed in this run.

## Existing Tool Considered

Plain git covers the need: `git push` with a lease, which the job already uses in `_push_with_lease`. No open, maintained tool or library checkpoints one run of a job in git. Temporal is rejected by ADR 0008. langgraph was rejected in #3054 for its own store. A hidden ref is plain git too, and design.md rejects it. The change adds about 50 lines and 25 test cases, and it deletes no code. Cost to build: about 40,000 tokens, under one day with two CI runs. Cost to keep: about 3,000 tokens each quarter. Cost to fix one miss: about 10,000 tokens.

## Dependencies

None. #3645 is closed. #4070 (phase marks and spend) and #4071 (typed result and hand-off) wait on this change.

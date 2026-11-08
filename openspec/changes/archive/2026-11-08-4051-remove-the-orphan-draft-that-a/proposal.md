# Proposal

## Why

The issue #4051 reports an orphan draft. `_stage_one` in `src/devops_cli/roadmap/stage/stage.py` pushes the branch, opens the draft pull request, and then writes the marks in one `set_marks` call. When that write fails, or when the worker dies between the push and the write, the branch and the draft stay on GitHub and the item records no `stage.pr`. The item then stays out of every later round, because `_Judge._held` holds an item for any pushed branch that names its issue number. `_reconcile` reads closed items only. A person must close the draft and delete the branch by hand.

A rule that deletes every pushed branch of an open item with no `stage.pr` is not safe. A branch of a person or of an agent for the same issue number looks the same, and `OpenPull` has no author field. The job needs a mark that proves the branch is its own.

## What Changes

- Add the key `stage.pending` to `StageRecordKey` in `src/devops_cli/roadmap/stores/store.py`. Its value is JSON with the branch name and the time: `{"branch": "<name>", "time": "<ISO 8601>"}`.
- `_stage_one` writes `stage.pending` with one `set_marks` before the push. The time is the `now` of the `StageWriter`. The marks write after the draft sets `stage.pending` to None with the other keys.
- Add a pass `_orphans` next to `_reconcile`. `plan_stage` calls it with its `now` and adds its results to `StagePlan.removals` and `StagePlan.kept`. The pass reads the open items that have `stage.pending` and no `stage.pr`, and it uses the branch name of the mark:
  - A mark younger than a constant age of 1 hour gives nothing. The age is the constant `CONST_ROADMAP_STAGE_ORPHAN_AGE_SECONDS` in `src/devops_cli/config/constants.py`, and no setting.
  - A branch that is not on `origin` gives `Removal(..., gone=True)`: only the record is cleared.
  - A pushed branch with `_foreign_commits` equal to 0 gives a `Removal`. The writer reads `store.open_pulls()` once per round, only when such a removal exists, closes the open pull request whose head is the branch, deletes the branch and clears the record.
  - A pushed branch with a commit of another author gives a `KeptBranch`, and costs no request.
- A pushed branch with no `stage.pending` mark is never touched.
- The dry run plan (`stage_requests` in `src/devops_cli/roadmap/request_plan.py`) lists the write of the mark before the push and the read of the open pull requests.
- Fix the documents that the new key makes wrong: `docs/ROADMAP_WORKFLOW.md` (the table of keys), `docs/roadmap/stage.md` (the orphan pass) and the docstring of `StageRecordKey`.
- Add a requirement to the `roadmap-stage` capability, because the stage job removing an orphan is behavior that a consumer observes.
- No setting is added, renamed, removed or tightened. The example and the live ConfigMap need no change. The test `tests/k8s` key-walk test of #4093 still proves that the example ConfigMap loads into `Settings`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A failed marks write leaves no orphan draft

## Impact

- Code: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_orphan.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/stage.md`
- Request cost: each staged item adds one `set_marks` call (2 requests: one read and one PATCH). A round with an orphan to remove adds one read of the open pull requests. Other rounds add none.
- Open point for review: the owner has not yet confirmed the intent-mark approach. It replaced the plain rule "delete the pushed branch by issue number and branch pattern", because that rule could delete the branch of a person or of another agent.
- Known gap, not widened: a closed item that holds `stage.pending` and no `stage.pr` is not an orphan of this pass. `_reconcile` clears a closed item only when it holds `stage.branch`.

## Feasibility

I checked the premise at `origin/main` by reading the code. I ran no GitHub request.

- `src/devops_cli/roadmap/stage/stage.py`: `_stage_one` calls `_commit_and_push`, then `_open_pull`, then one `set_marks` with BRANCH, PR, SHA, GROUPS and TEXT_HASH, then the labels, then the comment. `_open_pull` deletes the branch when the draft fails. `_label_pull` and `_label_needs_fix` catch `GitHubOperationError`. So only a failed marks write, or a death of the worker between the push and the write, leaves a pushed branch and a draft with no `stage.pr`.
- `_reconcile` reads the closed items with `stage.branch`. `_Judge._held` uses `issue_holder` in `src/devops_cli/git/worktree_add.py`, which holds an item for any pushed branch named with the issue number. This confirms that the item stays out of every round.
- `OpenPull` in `src/devops_cli/roadmap/stores/store.py` has `head_ref`, `number` and `draft`, and no author. `_foreign_commits` is the only author guard. This confirms why the plain rule is unsafe.
- `_remove_staged` clears `{key: None for key in StageRecordKey}`, so a new key is cleared with the rest. `RejectedPlan` in `src/devops_cli/roadmap/stage/stage_rejected.py` is the pattern for a JSON mark.
- `set_marks` in `src/devops_cli/roadmap/stores/github_store.py` makes one read and one PATCH, so the cost of 2 requests holds.
- The tests in `tests/roadmap/stage/test_roadmap_stage_orphan.py` run on the unchanged code, and 11 of 17 fail for the reasons above (`devops ci fail-to-pass --base origin/main`). The 6 that pass are guards: they prove that a mark of a young age, a recorded pull request and a closed item are left alone.
- I did not check how GitHub treats the open pull request of a deleted head branch. The pass closes the draft itself, so it does not depend on that behavior.

## Existing Tool Considered

No open, maintained tool or library repairs the state of one job in the record of an issue. The change reuses `_remove_staged`, `Removal`, `KeptBranch`, `_foreign_commits` and the JSON mark pattern of `stage.rejected`, all in the repository. The change builds one key, one write and one pass. The written cost: about 50,000 tokens and 2.5 hours to build, about 2,000 tokens each quarter to keep, and about 10,000 tokens and 0.5 hour to fix. No internal code is deleted.

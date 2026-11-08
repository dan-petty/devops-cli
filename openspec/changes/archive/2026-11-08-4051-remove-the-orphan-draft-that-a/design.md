# Design

## Decisions

- **Write an intent mark before the push.**: The mark `stage.pending` holds the branch name and the time. The job can then tell its own orphan from a branch of a person or of an agent, which has no mark.
- **Store the mark as JSON with the fields `branch` and `time`, as `stage.rejected` does.**: The pass uses the branch of the mark. A retitle between the failure and the next round changes the slug of the branch, but not the mark.
- **Write the mark with the `now` of the `StageWriter`.**: The tests set the clock, and the Service passes its own clock. The pass in `plan_stage` uses the `now` of the plan to judge the age.
- **Judge the orphans in `plan_stage`, like `_reconcile`, and read the open pull requests in the writer.**: `plan_stage` stays read-only, and a dry run makes no request. The plan holds a `Removal` for each orphan. `StageWriter.begin` reads `store.open_pulls()` once, only when a removal with a pushed branch exists, and finds the draft by its head.
- **Keep the age as the constant `CONST_ROADMAP_STAGE_ORPHAN_AGE_SECONDS` of 3600 seconds.**: A run in another clone can be in the middle of its publish. A setting would add a key to the ConfigMap for a value that nobody needs to tune.
- **Judge a mark that is as old as the limit.**: The rule is "younger than 1 hour is left alone", so a mark of exactly 1 hour is judged.
- **Judge the pass after the selection of the round.**: The item is still held by its pushed branch in the round that removes the branch. The next round plans it again. The plan facts (the groups with measured tokens and the hash of the text) were in the marks write that failed, so the planner must run again.
- **A bad record of the mark counts as no mark.**: A value that is not JSON, or that holds no branch or time, is logged and the pass leaves the item alone, as `recorded_rejection` does.
- **Do not widen to a closed item.**: A closed item that holds `stage.pending` and no `stage.pr` is not in the issue. It is a known gap.

## Rejected alternatives

- **Delete every pushed branch of an open item that has no `stage.pr`, found by issue number and branch pattern.**: `issue_holder` in `src/devops_cli/git/worktree_add.py` finds a branch by the issue number only. `OpenPull` in `src/devops_cli/roadmap/stores/store.py` has no author field, and `_foreign_commits` compares the commit authors with the `user.name` of the clone. A clone that has the identity of a person passes the guard, so the rule could delete the work of a person or of another agent. It would also defeat `_Judge._held`.
- **Write the branch in `stage.branch` before the push and use that key.**: `_reconcile` and the Service read `stage.branch` as the record of a finished stage. An early write would make a half-staged item look staged.
- **Search the pushed branches for the author `devops-roadmap[bot]`.**: The clone commits as the identity of the App, so a branch of an agent in the same clone has the same author. The mark is the only proof of intent.
- **Order the steps differently so that the marks write comes before the draft.**: The marks write needs the number of the draft pull request, and the record must not name a draft that does not exist.
- **Read the open pull requests in `plan_stage`.**: This adds a request to every round, and a dry run must make none.

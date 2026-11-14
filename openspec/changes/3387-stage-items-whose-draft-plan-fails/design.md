# Design

## Decisions

- **Push the re-stage with a lease on the recorded `stage.sha`.**: The worktree takes over the pushed branch and keeps its tip, so the new commit stacks on the old plan commit; `_rebase_onto_default` then replays the branch onto the default branch and can rewrite the tip, so the push is no fast-forward and the lease keeps a commit that a person pushed after the job read the branch.
- **Add the member `StageRecordKey.RESTAGE` in group 1, together with the rule that reads it.**: Groups 2, 3 and 4 read the record of an earlier re-stage, so the key must exist before the read and the selection are written; a later group that adds it leaves those groups without a key.
- **Read the plan of the draft with `folder_problems` of `src/devops_cli/roadmap/plan_check.py` on a `PlanFolder`.**: That function reads the change files with `read_change` and runs `check_proposal` with the known capability names and the tree, the same check that the stage job runs on its own reply, so the selection and the reply gate agree.
- **Name the stage reader `held_draft`, and keep it in `src/devops_cli/roadmap/stage/stage_held.py`.**: `read_draft` already exists at `src/devops_cli/roadmap/implement/implement_pull.py` for the draft readiness of the implement job, and a second reader of the same name would confuse the two jobs.
- **Decide the hold in a pure rule that takes the facts of the draft as arguments, and read those facts in one function beside it.**: The selection tests then pass the facts as data, as they already pass `holder_of`, and no test reaches the network.
- **Bound the re-stages with one record keyed by the hash of the text of the item.**: An unbounded rule calls the model on every round for a plan that always fails; a body edit is a new plan, as the count of the plan defects treats it.
- **Keep the current hold reason text for a passing plan, a review thread and a commit beyond the plan.**: The issue asks for the current reason on the three holds; a new reason for each cause would break the report and add no information.
- **Name the replaced draft in the comment of the item and record the re-stage in `stage.restage`.**: The comment is the report of the stage round and already names the pull request, so a person reads which draft the job replaced.
- **Count a changed path outside `openspec/changes/<issue>-<slug>/` as a commit beyond the plan.**: The change folder is the plan, so any other path is work that the item did not ask for; a commit after the plan commit is often the plan itself.
- **Update the same draft with `update_pull`, and open no second pull request.**: Two records for one item lose the review threads, and the record `stage.pr` would name a pull request that the job abandoned.
- **Keep the text of `The job leaves out the items it must not stage` under the OpenSpec limit of 500 characters, and give the bound its own added requirement.**: The held-item sentence with the re-stage condition is 485 characters, and the bound of one re-stage is the added requirement `The stage job re-stages a failing draft plan once`.
- **List `tests/roadmap/stores/test_comment_repeat.py` in the `reads` of group 1 and run it in that group's `verify`.**: Group 1 changes `src/devops_cli/roadmap/stores/store.py`, and that test imports the module, so a break in the store shows in the group that makes it.

## Rejected alternatives

- **Close the draft and open a new pull request for the same branch.**: Two records for one item lose the review threads, and the record `stage.pr` would name a pull request that the job abandoned; the issue asks for the same branch and one draft.
- **Read the check runs of the draft pull request instead of running the plan check.**: The plan check is a gate of the stage job, not a required check of `docs/adr/0004-ci-is-the-authoritative-gate.md`, so no check run reports it.
- **Re-stage on every round while the plan keeps failing.**: A plan that always fails then spends the model budget on every round; one recorded re-stage, then the hold, stops it.
- **Read REST issue comments as review threads.**: A comment carries no resolved state, and the review threads come from the `reviewThreads` query of `src/devops_cli/github/pr_threads.py`.
- **Reset the branch to the default branch and amend the old plan commit.**: The worktree takes over the branch tip, so a reset would discard a commit that a person may have read; the new commit on the tip and the updated draft keep the record.
- **Build the proposal of the draft by hand and call `check_proposal` directly.**: `src/devops_cli/roadmap/plan_read.py:def read_change` and `src/devops_cli/roadmap/plan_check.py:def folder_problems` already turn the change files into a proposal and run every gate, so a second builder would drift from the command.
- **Name the stage reader `read_draft` as well.**: `src/devops_cli/roadmap/implement/implement_pull.py:251:def read_draft(` already holds that name for the draft readiness of the implement job, so the stage reader is named `held_draft`.

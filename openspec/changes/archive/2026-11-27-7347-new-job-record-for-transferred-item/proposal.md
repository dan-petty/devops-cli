# Proposal: #7347

## Why

An issue that a person transfers to a repository keeps its body (#7347). The body holds the job record of the roadmap Service from the repository that the issue left: branch names, pull request numbers and Job names. The rows of the new repository read that record as their own. The stage row then fails for such an item in each round with `step=apply class=ci_infra`, and writes `stage.failed_error = GitHubNotFoundError` into the item each time, because `staged_plans` and `closed_plans` read the pull request of `stage.pr`, and the repository has no pull request with that number.

## What Changes

- **The read.** A record is the record of the issue that a job wrote it for. `own_record` of `src/devops_cli/roadmap/stores/store.py` gives an empty record for a block that was written for another issue: a branch that the block names (`stage.branch`, `implement.branch`, the branch of the intent mark `stage.pending`) names another issue number. Each reader takes the block through it: `_IssuePayload.record` of the GitHub store, for one issue and for the listing, and `issue_from_event` of the brain. The Item and the issue of such a read hold `foreign_record`.
- **One write replaces the block.** `record_block` builds the block of each record write. For a block that was written for another issue it merges into no key: the new block holds the keys of the write, and a write with no mark leaves the body with no block. For the record of the issue, the block is the one that the base writes for the same record, so no item gets a body write only because of this release.
- **The stage round.** `read_stage_round` lists the items that hold `foreign_record` (`StagePlan.resets`), and `StageWriter.begin` sends one write with no mark for each, before its removals. The plan of a run lists them under `## Records to replace`.
- **Proof at each use.** `recorded_plan` gives the plan pull request of an item as its record names it: the number of `stage.pr` and the branch of `stage.branch`, and only when the branch names the item. A row takes a pull request as that plan only when its head branch is the recorded branch. The `watch` row uses the rule in the GraphQL round, in the REST round, in the scoped round and in the read of the plans that are no more open. The stage round uses it for the draft of a closed item and for the read of a plan that closed with no merge. The round of `stage_ready.py` and the selection of the implement job compare the head branch of the recorded pull request in the same way. A recorded branch is the branch of an item only when it names the item: the cleanup of a closed item, the orphan of an intent mark and the `open` row use this rule. The open step records the head branch of a plan with its number, so each writer of `stage.pr` also writes `stage.branch`.
- `docs/ROADMAP_WORKFLOW.md` and `docs/roadmap/stage.md` give the rules.

A consumer observes the result of a read, the block that a write leaves, the requests of a round and the plan text of `devops roadmap stage`, so the change carries spec deltas. It fits one pull request.

## Capabilities

### Modified Capabilities

- `roadmap-item-labels`: A record is the record of the issue that it was written for, Each reader gives an empty record for the block of another issue, One record write replaces a record of another issue
- `roadmap-stage/round`: A stage round replaces the record of another issue, A recorded pull request is the plan of an item only on the recorded branch, The draft of a closed item is the open pull request on its staged branch, A recorded branch is the branch of an item only when it names the item
- `roadmap-watch-row`: The watch row takes a plan pull request by its number and its head branch, Each round of the watch row reads the head branch before it takes a plan
- `roadmap-stage/open`: The open row takes a recorded branch that names the item, The open step records the head branch of a plan
- `roadmap-stage/ready`: The stage ready round takes a plan pull request by its number and its head branch
- `roadmap-implement-job/selection`: A recorded draft is the draft of an item only on the branch of the item

## Impact

- Code: `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stores/github_store.py`, `src/devops_cli/roadmap/stores/brain_issues.py`, `src/devops_cli/roadmap/watch_row.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_rejected.py`, `src/devops_cli/roadmap/stage/stage_pending.py`, `src/devops_cli/roadmap/stage/stage_ready.py`, `src/devops_cli/roadmap/implement/implement.py`, `src/devops_cli/roadmap/open_row.py`, `src/devops_cli/roadmap/steps/open.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/stores/test_roadmap_record_owner.py` (new), `tests/roadmap/stage/test_roadmap_stage_record_owner.py` (new), `tests/roadmap/test_roadmap_watch_plan_branch.py` (new), `tests/support/fakes/roadmap_store.py` (the in-memory store reads and writes a block as the GitHub store does), and the tests that hold a plan with no recorded branch or a recorded branch of another issue number
- Documents: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/stage.md`
- GitHub requests: the reset costs one `PATCH` for each item that holds a block of another issue, one time. The cleanup of a closed item whose branch is pushed reads the open pull requests one time in a round, as the cleanup of an orphan does. The `watch` row reads one more field, `headRefName`, in its one GraphQL query. No other read is added.
- The snapshot of the listing: `IssueRecord` gets the field `foreign_record`, so the schema key of the snapshot changes and each lane reads its listing in full one time after the release.
- Deleted internal code: none.

## Feasibility

- The cause is in the source at the base commit `8c485655e`. `decode_job_record` of `src/devops_cli/roadmap/stores/store.py` takes a block with no fact of the issue that holds it, and `encode_job_record` merges each write into the block. `staged_plans` of `src/devops_cli/roadmap/stage/stage_rejected.py` takes `stage.pr` of each open New or Ready item, and `closed_plans` reads that pull request.
- The live Service showed the result on 2026-11-26 (devops-cli 0.223.2), as #7347 records it: one failure of the stage row for the item in each round, about every 4 minutes.
- The new tests fail on the base: `uv run devops ci fail-to-pass --base origin/main` gave 38 failed on the base, each of them a new or a changed case. The 7 cases of the 3 new test modules that pass on the base are the 6 cases of a pull request or a branch that is the recorded one of its item, and the case of a write to the record of the issue. They must read and write as before.
- A job names each branch that it records with the number of its item. `StageTarget.branch` of `src/devops_cli/roadmap/stage/stage.py` is `branch_name(self.item.number, self.type_, self.slug)`, and `issue_of_branch` of `src/devops_cli/git/branch_form.py` reads the number back. So the branch of a block tells the issue number that the block was written for.
- The set of the claim is the places that take the number of `stage.pr` from a record: `git grep -nE "StageRecordKey\.PR\b" origin/main -- src` gives 24 lines at the base. Each use that this change does not touch has a proof of the item of its own before a write: it writes the key with its branch, it reads the key for a display, a phase or a kind and sends no request for the pull request, or it compares the head branch, the head commit or the title of the pull request with the item.
- The set of the places that take a recorded branch for a write is 3: the staged branch of a closed item (`_reconcile`), the branch of an intent mark (`orphan_mark`) and the delivery branch of the `open` row (`open_candidates`). Each one now takes the branch only when it names the item.

## Existing Tool Considered

The need is a comparison of a record block with the issue that holds it. No library holds this rule of the store. The change builds no parser: `issue_of_branch` of `src/devops_cli/git/branch_form.py` reads the issue number of a branch, and the standard library reads the JSON of the intent mark. Cost to build: about 250 lines of source and 3 test modules, about 900 thousand tokens and 8 hours. The change deletes no internal code.

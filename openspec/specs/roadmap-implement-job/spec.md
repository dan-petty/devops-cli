# roadmap-implement-job Specification

## Purpose
What `devops roadmap implement` does as a job: which Staged items it takes, how it runs the task groups of a change, what it writes to git and to GitHub, and when it stops an item, so that a Staged item becomes a ready pull request with no person at the keyboard, and a person still merges.

## Requirements

### Requirement: The job runs steps only in a runner
The job SHALL run a step only when the setting `roadmap.implement.in_runner` is true. With it false, `--confirm` SHALL refuse before it reads a repository, writes to git or to GitHub, or calls a model, and SHALL name the setting. `--plan` and `--dry-run` SHALL run a step in no case.

#### Scenario: A workstation or the Service pod
- **WHEN** `devops roadmap implement --confirm` runs with `roadmap.implement.in_runner` false
- **THEN** the command exits 1, the message names `roadmap.implement.in_runner`, the model is not asked, and no git command and no GitHub request runs

### Requirement: The job takes a Staged item that the filter names
A Staged item SHALL hold `stage.pr` and `stage.branch` in its record, its branch SHALL be on `origin`, and its draft pull request SHALL be open. The default filter SHALL be `status=ready`, `priority=p0-critical`, `priority=p1-high`, `type=bug` and `effort=low`. The values of one family are alternatives and the families all apply. `--limit` SHALL default to 1, and the highest priority comes first.

#### Scenario: The default filter
- **WHEN** the roadmap holds a Staged Ready P1 bug of low effort, a Staged Ready P1 bug of high effort, and a Staged Ready P3 bug of low effort
- **THEN** the plan selects the first item, and does not name the other two, which the filter does not name

### Requirement: The job leaves out an item and says why
The job SHALL leave out, with a reason in the plan, an item that the filter names and that is not Ready, is not Staged, holds `implement.stopped`, has an author who is not the owner, a member or a collaborator, has a commit past the default branch by anyone but the App, is held by a worktree, or whose pull request is not an open draft.

#### Scenario: An item that is not Staged
- **WHEN** a Ready P1 bug of low effort has no `stage.pr` in its record
- **THEN** the plan leaves it out with the reason that it is not Staged

#### Scenario: An item with a stop on record
- **WHEN** a Staged item holds `implement.stopped`
- **THEN** the plan leaves it out with the reason that names the stop and the comment `implement: retry`

#### Scenario: A commit by another author
- **WHEN** the branch of a Staged item holds a commit whose author is not the App
- **THEN** the plan leaves the item out with the reason that names the author

#### Scenario: The pull request is not an open draft
- **WHEN** the pull request of a Staged item is ready for review, or closed
- **THEN** the plan leaves the item out with the reason that its pull request is not an open draft

#### Scenario: A retry comment
- **WHEN** a Staged item holds `implement.stopped` and a comment `implement: retry` by the owner, made after the stop comment
- **THEN** the plan selects the item, and the run clears `implement.stopped` before the first step

#### Scenario: A retry comment by a stranger
- **WHEN** the comment `implement: retry` comes from a user who is not the owner, a member or a collaborator
- **THEN** the item stays left out

### Requirement: The job runs the unticked groups in order and finishes the change
For each selected item the job SHALL set Status to In Progress and rebase the staged branch onto the fetched default branch. A conflict SHALL stop the item before any step. The job SHALL run one step, in order, for each group of `tasks.md` that has an unticked task.

#### Scenario: A group that is done
- **WHEN** every task of group 1 is ticked on the branch
- **THEN** the job runs a step for group 2 only

#### Scenario: A conflict on the rebase
- **WHEN** the default branch holds a change that conflicts with a commit of the staged branch
- **THEN** no step runs, the item is stopped with the step `rebase`, and the clone holds no rebase in progress

### Requirement: The job commits the documentation and the archive, and pushes
After the last group the job SHALL run `uv run devops docs generate --sync-readme` and commit its changes, then `uv run devops openspec archive <change>` and commit its changes, then push. The job SHALL run each of these outside the agent shell.

#### Scenario: Two groups
- **WHEN** a Staged low-effort P1 bug has a change with two unticked groups, and both steps pass
- **THEN** the branch holds the commit of the stage job, one commit for each group, one commit for the documentation and one commit for the archive, in that order, and `origin` holds the same branch

### Requirement: The job rewrites the pull request after the push
After the push the job SHALL set the body of the pull request to `Closes #N`, the why of the `proposal.md`, and the line `Change: openspec/changes/archive/<date>-<change>/` with the archive folder in a code span, in this order. The text of the proposal SHALL be on one line, with a handle or a link of another repository in a code span, and at most 1,000 characters. The job SHALL post the outcome of each step as one comment on the pull request, and SHALL put nothing of it in the body.

#### Scenario: The body
- **WHEN** the job finishes the change of item 7
- **THEN** the body of the pull request starts with `Closes #7`, holds the why of the proposal, and ends with the `Change:` line of the archive folder

### Requirement: One fix step for a failed check
When the settled checks of the pull request hold a failed one, the job SHALL run the fix step once for the item, with the log of the failed run as input, SHALL rebase, push, and watch the checks again. A second failed check SHALL stop the item. A check that does not settle within `CONST_ROADMAP_IMPLEMENT_MONITOR_TIMEOUT_SECONDS`, an unresolved review thread and a merge conflict SHALL stop the item and run no fix step.

#### Scenario: A check fails once
- **WHEN** the first watch shows a failed check, the fix step passes, and the second watch shows every check passed
- **THEN** the job pushes the fix commit, marks the pull request ready, and sets Status to In Review

#### Scenario: A check fails twice
- **WHEN** the check fails again after the fix step
- **THEN** the item is stopped with the step `checks`, the pull request stays a draft, and no second fix step runs

#### Scenario: The watch sees the old head
- **WHEN** the first read after a push still shows the previous head commit of the pull request
- **THEN** the job reads again, and judges only a status whose head is the pushed commit

### Requirement: A pull request that passes its checks is marked ready
When every check passed and no review thread is open, the job SHALL run `gh pr ready`, set Status to In Review, record `implement.group`, `implement.sha`, `implement.pr` and `implement.spend`, and post one comment on the issue with the pull request and the spend. The job SHALL NOT merge.

#### Scenario: The finish
- **WHEN** the checks pass
- **THEN** `gh pr ready <pr>` ran once, Status is In Review, the record holds the number of the pull request and the last commit, and the issue holds one comment that starts with the marker and names the pull request

### Requirement: A stopped item goes back to Ready and is never retried
When a step, the rebase, the documentation, the archive, a push or the checks stop the item, the job SHALL post a comment that starts with the marker and names the step, the reason and the last message of the agent, SHALL set Status to Ready, and SHALL record `implement.stopped` with the step. It SHALL push the commits of the steps that passed. The job SHALL NOT run the item again until a retry comment clears the record. The job SHALL go on to the next selected item.

#### Scenario: A step stops
- **WHEN** the step of group 2 reports stopped
- **THEN** Status is Ready, `implement.stopped` is `group 2`, the comment holds the reason, `origin` holds the commit of group 1, and the pull request is still a draft

#### Scenario: A conflict on the rebase before a push
- **WHEN** the default branch gains a change that conflicts with the branch after the last group, or after the fix step
- **THEN** the job aborts the rebase, `origin` holds the commits that passed, Status is Ready, and `implement.stopped` is `push`

### Requirement: The job record
The job SHALL keep `implement.group` (the last group that passed), `implement.sha` (the commit it ended on), `implement.pr` (the pull request), `implement.stopped` and `implement.spend` in the job record of the item. The spend SHALL be the requests, input tokens and output tokens of every step the job ran.

#### Scenario: Spend
- **WHEN** two steps used 3 and 4 requests
- **THEN** the record of the spend holds 7 requests

### Requirement: A dry run makes no request
`--dry-run` SHALL make no request, SHALL return the plan type marked as a dry run, and SHALL list the reads and the writes of a run in order.

#### Scenario: Dry run
- **WHEN** `devops roadmap implement --dry-run` runs
- **THEN** no git command runs, no GitHub request is made, and the output lists the requests of a run

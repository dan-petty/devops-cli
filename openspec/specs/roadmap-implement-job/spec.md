# roadmap-implement-job Specification

## Purpose
What `devops roadmap implement` does as a job: which Staged items it takes, how it runs the task groups of a change, what it writes to git and to GitHub, and when it stops an item, so that a Staged item becomes a ready pull request with no person at the keyboard, and a person still merges.

## Requirements

### Requirement: The job runs steps only in a runner
The job SHALL run a step only when the setting `roadmap.implement.in_runner` is true. With it false, `--confirm` SHALL run no step. It SHALL start a runner Job for the Item that `--item` names (see "A workstation starts the runner Job for one Item"), or refuse before it reads a repository, writes to git or to GitHub, or calls a model, and name the supported command. `apply_implement` SHALL raise `RoadmapImplementError` that names the setting. `--plan` and `--dry-run` SHALL run a step in no case.

#### Scenario: A workstation or the Service pod
- **WHEN** `devops roadmap implement --confirm` runs with `roadmap.implement.in_runner` false and no `--item`
- **THEN** the command exits 1, the message names `roadmap.implement.in_runner` and `devops k8s run-job --template runner`, the model is not asked, and no git command, no GitHub request and no cluster request runs

#### Scenario: The library
- **WHEN** `apply_implement` runs with `roadmap.implement.in_runner` false
- **THEN** it raises `RoadmapImplementError` that names `roadmap.implement.in_runner`, the model is not asked, and no git command and no GitHub request runs

### Requirement: The job takes a Staged or a Planned item that the filter names
A Staged item SHALL have a recorded branch on `origin` and an open draft pull request. The pair is `implement.branch` and `implement.pr`, else `stage.branch` and `stage.pr`. A Planned item SHALL have no recorded branch on `origin` and its change folder on `origin/<default branch>`. A branch on `origin` makes it Staged. The default filter SHALL be `status=ready` and `status=planned`. `--limit` SHALL default to 1.

#### Scenario: The default filter
- **WHEN** the roadmap holds a Staged Ready P1 bug of low effort, a Staged Ready P1 bug of high effort, a Staged Ready P3 feature of low effort, and a Staged Ready P2 bug of medium effort
- **THEN** the plan selects the first item when the limit is 1, and with a limit of 2 it selects the first item and the feature; it does not select the bug of high effort, and it does not select the bug of medium effort, which the fallback pass takes only when no low-effort item is selectable

#### Scenario: A plan on the default branch and a branch that is gone
- **WHEN** a Ready P1 bug of low effort has a record with a merged `stage.pr` and a `stage.branch` that is not on `origin`, and `origin/main` holds its change folder
- **THEN** the plan selects it as a Planned item, with the branch `fix/<issue>-<slug>` and no pull request, and the slug is the one of the change folder

#### Scenario: A plan on the default branch and a branch that is there
- **WHEN** the staged branch of the item is on `origin` with an open draft, and `origin/main` also holds the change folder
- **THEN** the plan selects the item with its staged branch and its pull request, as a Staged item

#### Scenario: Two Planned items
- **WHEN** two Ready P1 bugs of low effort have their change folders on `origin/main`, and the limit is 2
- **THEN** the plan selects both, the lower number first

#### Scenario: A Planned feature
- **WHEN** a Ready P2 item titled `feat(cli): add a flag`, of low effort, has its change folder on `origin/main` and no branch
- **THEN** the plan selects it as a Planned item with the branch `feat/<issue>-<slug>`

#### Scenario: An item with the Status Planned
- **WHEN** a P1 bug of low effort has the Status Planned and its change folder is on `origin/main`
- **THEN** the plan selects it as a Planned item

### Requirement: The job takes the highest priority first
A run SHALL take the items that the filter names with the highest priority first. Among equal priorities it SHALL take an item with no entry in `implement.digest_clears` before an item with one, and then the lowest issue number first. An item with no priority SHALL go last.

#### Scenario: Priority order
- **WHEN** the roadmap holds a Staged Ready P3 item and a Staged Ready P0 item, both of low effort
- **THEN** the plan selects the P0 item first

#### Scenario: A new item before a retried item
- **WHEN** two items of one priority are eligible, the lower number has an entry in `implement.digest_clears`, and the higher number has none
- **THEN** the plan selects the higher number first

#### Scenario: Priority before attempt state
- **WHEN** an item of priority P1 has an entry in `implement.digest_clears` and an item of priority P2 has none
- **THEN** the plan selects the P1 item first

### Requirement: The job leaves out an item and says why

The job SHALL leave out, with a reason in the plan, an item that the filter names and that is neither Ready nor Planned, is neither Staged nor Planned, holds `implement.stopped`, fails the check of `roadmap-author-trust`, has a commit past the default branch by anyone but the App other than a clean merge, is held by a worktree, or whose pull request is not an open draft. A clean merge is a merge commit whose tree is the one that `git merge-tree --write-tree` gives for its two parents.

#### Scenario: An item that is not Staged
- **WHEN** a Ready P1 bug of low effort has no `stage.pr` in its record and no change folder on `origin/main`
- **THEN** the plan leaves it out with the reason that it is neither Staged nor Planned

#### Scenario: An item with a stop on record
- **WHEN** a Staged item holds `implement.stopped`
- **THEN** the plan leaves it out with the reason that names the stop and the comment `implement: retry`

#### Scenario: An item of a bot with no approval
- **WHEN** a Staged item of the Service App's bot has no approval of refine's review, or its body changed after the review
- **THEN** the plan leaves it out with the reason that no review approved its body as it is now

#### Scenario: A commit by another author
- **WHEN** the branch of a Staged item holds a commit whose author is not the App
- **THEN** the plan leaves the item out with the reason that names the author

#### Scenario: A clean merge by a person
- **WHEN** the branch of a Staged item holds a commit by the App and a merge commit by a person whose tree is the tree of the clean merge of its parents
- **THEN** the plan does not leave the item out for that merge commit

#### Scenario: A merge by a person that changes a file
- **WHEN** the branch of a Staged item holds a merge commit by a person whose tree differs from the tree of the clean merge of its parents, because the merge changed a file or resolved a conflict
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

#### Scenario: A closed Planned item
- **WHEN** `--item N` names a closed issue whose change folder is on `origin/main`
- **THEN** the plan leaves it out because it is closed

#### Scenario: The item of a Job that runs
- **WHEN** the Service set an item In Progress for the Job it made, and the Job plans the item with `--item`
- **THEN** the plan selects the item

#### Scenario: An item that is In Progress with no Job
- **WHEN** an item is In Progress and its record names no Job
- **THEN** the plan leaves it out with its Status

### Requirement: The job leaves out a Planned item that is held, archived or incomplete

The job SHALL leave out, with a reason in the plan, a Planned item that a branch or worktree holds, that is archived, that has no branch name or no `tasks.md`, or whose every task is ticked.

#### Scenario: A Planned item that another agent holds
- **WHEN** the change folder of a Ready item is on `origin/main` and `origin` holds a branch `fix/<issue>-other` for it, which is not its recorded branch
- **THEN** the plan leaves the item out with the reason of the held issue

#### Scenario: A Planned item whose change is archived
- **WHEN** `origin/main` holds only the archived folder of the item
- **THEN** the plan leaves the item out and says that its change is archived on `main`

#### Scenario: A Planned item whose change has no tasks.md
- **WHEN** the change folder of a Planned item on `origin/main` holds no `tasks.md`, and a second Planned item is valid
- **THEN** the plan leaves the first item out with a reason that names the folder and the error of git, and selects the second item

#### Scenario: A Planned item with every task ticked
- **WHEN** the `tasks.md` of the change folder on `origin/main` has no unticked task
- **THEN** the plan leaves the item out and says that every task is ticked

### Requirement: The job runs the unticked groups in order and finishes the change
For each selected item the job SHALL set Status to In Progress and rebase the staged branch onto the fetched default branch. A conflict SHALL stop the item before any step. The job SHALL run one step, in order, for each group of `tasks.md` that has an unticked task.

#### Scenario: A group that is done
- **WHEN** every task of group 1 is ticked on the branch
- **THEN** the job runs a step for group 2 only

#### Scenario: A conflict on the rebase
- **WHEN** the default branch holds a change that conflicts with a commit of the staged branch
- **THEN** no step runs, the item is stopped with the step `rebase`, and the clone holds no rebase in progress

### Requirement: The job commits the documentation and the archive, and pushes
After the last group the job SHALL run `uv run devops docs generate --sync-readme` and commit its changes, then `uv run devops openspec archive <change>` and commit its changes, then rebase, run the scoped checks, then push. The job SHALL run each of these outside the agent shell.

#### Scenario: Two groups
- **WHEN** a Staged low-effort P1 bug has a change with two unticked groups, and both steps pass
- **THEN** the branch holds the commit of the stage job, one commit for each group, one commit for the documentation and one commit for the archive, in that order, and `origin` holds the same branch

### Requirement: The job rewrites the pull request after the push
After the push the job SHALL set the body of the pull request to `Closes #N`, the why of the `proposal.md`, and the line `Change: openspec/changes/archive/<date>-<change>/` with the archive folder in a code span, in this order. The text of the proposal SHALL be on one line, with a handle or a link of another repository in a code span, and at most 1,000 characters. The job SHALL post the outcome of each step as one comment on the pull request, and SHALL put nothing of it in the body.

#### Scenario: The body
- **WHEN** the job finishes the change of item 7
- **THEN** the body of the pull request starts with `Closes #7`, holds the why of the proposal, and ends with the `Change:` line of the archive folder

### Requirement: A failed check of the pull request gets bounded fix steps
When the settled checks of the pull request hold a failed one, the job SHALL run a fix step with the log of the failed run, rebase, run the scoped checks, push, and watch again. It SHALL do so at most `roadmap.implement.repair_rounds` times, with a comment on the pull request for each round. A check that still fails after the last round, a check that does not settle within `CONST_ROADMAP_IMPLEMENT_MONITOR_TIMEOUT_SECONDS`, an unresolved review thread and a merge conflict SHALL stop the item.

#### Scenario: A check fails once
- **WHEN** the first watch shows a failed check, the fix step passes, and the second watch shows every check passed
- **THEN** the job pushes the fix commit, marks the pull request ready, and sets Status to In Review

#### Scenario: A check fails twice
- **WHEN** the check fails after the first and the second fix step, and passes after the third
- **THEN** two fix steps ran, the job marks the pull request ready, and the pull request holds one comment for each round

#### Scenario: A check fails in every round
- **WHEN** the check fails after each of the 3 fix steps, and `repair_rounds` is 3
- **THEN** the item is stopped with the step `checks`, the pull request stays a draft, and no fourth fix step runs

#### Scenario: No round
- **WHEN** `repair_rounds` is 0 and a check fails
- **THEN** the item is stopped with the step `checks` and no fix step runs

#### Scenario: The watch sees the old head
- **WHEN** the first read after a push still shows the previous head commit of the pull request
- **THEN** the job reads again, and judges only a status whose head is the pushed commit

### Requirement: A pull request that passes its checks is marked ready
When `draft_readiness` answers ready for the implement pull request and no review thread is open, the job SHALL run `gh pr ready`, set Status to In Review, record `implement.group`, `implement.sha`, `implement.pr` and `implement.spend`, and post one comment on the issue with the pull request and the spend. When it answers wait or refuse, the job SHALL stop the item with the reason and SHALL NOT run `gh pr ready`. The job SHALL NOT merge.

#### Scenario: The finish
- **WHEN** the checks pass
- **THEN** `gh pr ready <pr>` ran once, Status is In Review, the record holds the number of the pull request and the last commit, and the issue holds one comment that starts with the marker and names the pull request

#### Scenario: A task group stays unticked
- **WHEN** the archived `tasks.md` of the job holds an unticked task in group 2 after the archive step
- **THEN** the item is Blocked with a reason that names group 2, `gh pr ready` ran never, and the class of the failure is `plan_defect`

#### Scenario: A check starts after the watch
- **WHEN** a check run of the head is running when the job reads the check runs before it marks the pull request ready
- **THEN** the item is Blocked with the reason that a check runs, and `gh pr ready` ran never

### Requirement: A stopped item is Blocked and the job does not retry it
When a step, the rebase, the documentation, the archive, a push or the checks stop the item, the job SHALL post a comment that starts with the marker and names the step, the reason and the last message of the agent, SHALL set Status to Blocked, and SHALL record `implement.stopped` with the step. It SHALL push the commits of the steps that passed. The job SHALL NOT run the item again until a clear rule removes the record. The job SHALL go on to the next selected item.

#### Scenario: A step stops
- **WHEN** the step of group 2 reports stopped
- **THEN** Status is Blocked, `implement.stopped` is `group 2`, the comment holds the reason, `origin` holds the commit of group 1, and the pull request is still a draft

#### Scenario: A conflict on the rebase before a push
- **WHEN** the default branch gains a change that conflicts with the branch after the last group, or after the fix step
- **THEN** the job aborts the rebase, `origin` holds the commits that passed, Status is Blocked, and `implement.stopped` is `push`

### Requirement: The stop comment cuts a long reason
The job SHALL cut the reason of a stop to `CONST_ROADMAP_IMPLEMENT_REASON_CHARS` characters after it masks secrets in it, so that the stop comment stays below the limit of GitHub.

#### Scenario: A reason that is too long
- **WHEN** a step stops with a reason longer than `CONST_ROADMAP_IMPLEMENT_REASON_CHARS` characters
- **THEN** the comment holds the first `CONST_ROADMAP_IMPLEMENT_REASON_CHARS` characters of the reason

### Requirement: The job record
The job SHALL keep `implement.group` (the last group that passed), `implement.sha` (the commit it ended on), `implement.branch` (the branch of the pull request), `implement.pr` (the pull request), `implement.stopped`, `implement.spend` and `implement.trace` in the job record of the item. The spend SHALL be the requests, input tokens and output tokens of every step the job ran.

#### Scenario: Spend
- **WHEN** two steps used 3 and 4 requests
- **THEN** the record of the spend holds 7 requests

#### Scenario: The branch
- **WHEN** the job takes a Staged item and a Planned item to a ready pull request
- **THEN** the record of each holds its branch and its pull request

#### Scenario: The trace
- **WHEN** the job takes an item to a ready pull request
- **THEN** the record holds `implement.trace` with the events of the steps, the scoped checks and the commands of the job

### Requirement: A dry run makes no request
`--dry-run` SHALL make no request, SHALL return the plan type marked as a dry run, and SHALL list the reads and the writes of a run in order.

#### Scenario: Dry run
- **WHEN** `devops roadmap implement --dry-run` runs
- **THEN** no git command runs, no GitHub request is made, and the output lists the requests of a run

### Requirement: The Service submits one implement Job per repository at a time
The status lane of the Service SHALL have a row `implement` after the row `metrics`, due every ten minutes and on a first run, that runs in the job clone of the lane. A round SHALL list the Jobs that carry the label of the repository, and SHALL create no Job while one of them has not ended. Else it SHALL plan the Staged and Planned items that the default filter names, and create one Job from CronJob `devops-cli-runner` for the first of them. The Service SHALL run no step itself.

#### Scenario: A Staged low-effort P1 bug
- **WHEN** the Kubernetes API is faked with CronJob `devops-cli-runner`, and a round of the row runs on a Staged Ready P1 bug of low effort
- **THEN** the API receives one Job create, and a second round with the Job still running creates no second Job

#### Scenario: A running Job of another item
- **WHEN** a Job of the repository has no Complete or Failed condition, and a second Staged item is ready
- **THEN** the round creates no Job

#### Scenario: The template is missing
- **WHEN** CronJob `devops-cli-runner` does not exist
- **THEN** the round raises an error that names the CronJob and the namespace, and creates no Job

#### Scenario: A Planned item
- **WHEN** the plan of a Ready P1 bug of low effort is on `origin/main` and its branch is gone
- **THEN** the round creates one Job with the args of that item

### Requirement: The Job gets the args of its item and a token for one repository
The Job SHALL have the args `roadmap implement --repo <repo> --item <number> --confirm` and the environment variable `DEVOPS_CLI_SERVICE_GITHUB_APP_TOKEN_REPOSITORY` set to the repository. The round SHALL record the name of the Job in `implement.job` and clear `implement.job_state` before it creates the Job.

#### Scenario: The Job is read
- **WHEN** a round created the Job for item 1 of `example/project`
- **THEN** the container args are those args, the variable holds `example/project`, and the record of item 1 holds the Job's name and no `implement.job_state`

### Requirement: A later round reports the Job that ended
A round SHALL read the Job of each item whose record holds `implement.job` and no `implement.job_state`. For a Job that ended (Complete or Failed), it SHALL comment on the item, with the marker of the implement job, the state and the last lines of the pod's log, decoded and masked of secrets, in a fenced block, and record `implement.job_state` as `succeeded` or `failed`. A Job that no longer exists SHALL be recorded as `gone`. A log that the API refuses SHALL not block the report.

#### Scenario: A Job that succeeded
- **WHEN** the Job of an item has the condition Complete and the item is In Review
- **THEN** the item gets a comment with the state `succeeded`, `implement.job_state` is `succeeded`, and the Status stays In Review

#### Scenario: A log with a check mark and several lines
- **WHEN** the log of the pod is the bytes of two lines, the first with a check mark and the second with a token
- **THEN** the comment holds a fenced block with the two lines on two lines, the check mark as the character, the token masked, and no `b'` prefix

#### Scenario: A log with a run of backticks
- **WHEN** a line of the log holds a run of three backticks
- **THEN** the fence of the block is longer than that run

#### Scenario: A log the API refuses
- **WHEN** the API refuses to read the log of the pod of a Job that failed
- **THEN** the item gets the comment without a log, `implement.job_state` is `failed`, and the next round raises no error

#### Scenario: A Job that is gone
- **WHEN** the record of an item names a Job that the API does not list
- **THEN** `implement.job_state` is `gone`

### Requirement: A Job that leaves its item eligible stops the item
When a reported Job leaves its item neither In Review nor stopped, the round SHALL set the item Blocked and record `implement.stopped` as `job`. No Job SHALL be created for the item before a clear rule runs.

#### Scenario: A Job that failed
- **WHEN** the Job of an item has the condition Failed, the item is In Progress, and no continuation applies to it
- **THEN** the item gets a comment with the state `failed` and the tail of the log
- **AND** `implement.job_state` is `failed`, the Status is Blocked, and `implement.stopped` is `job`
- **AND** the next round creates no Job for the item

### Requirement: A runner process cannot be read by its own shell
Before the first step, the job in a runner SHALL clear the dumpable flag of its own process with `prctl(PR_SET_DUMPABLE, 0)`, so that no child reads `/proc/<pid>/environ` of the job. A call that the kernel refuses SHALL make `apply_implement` raise `RoadmapImplementError`, and no step SHALL run. The step of the agent SHALL get none of the variables of the job, except `UV_CACHE_DIR`, `UV_PYTHON` and `PYTEST_XDIST_AUTO_NUM_WORKERS`.

#### Scenario: A child reads the environment of its parent
- **WHEN** a process sets the flag, holds a variable in its starting environment, and starts a child that opens `/proc/<parent pid>/environ`
- **THEN** the child gets `PermissionError`

#### Scenario: The refusal
- **WHEN** `prctl` returns -1 and `apply_implement` runs a plan
- **THEN** `apply_implement` raises `RoadmapImplementError` that names `PR_SET_DUMPABLE`, and no step, no model request and no program runs

### Requirement: The job runs no step without a token for its repository
Before any step, `devops roadmap implement --confirm` and `apply_implement` SHALL raise `RoadmapImplementError` unless the process acts as the GitHub App and `service.github_app.token_repository` equals the repository of the plan. The message SHALL name the setting. A Job made by `devops k8s run-job` SHALL get that setting from `--repo`, and `run-job` SHALL refuse the runner template without `--repo`.

#### Scenario: A token for every repository
- **WHEN** `service.github_app.token_repository` is empty or names another repository
- **THEN** `apply_implement` raises `RoadmapImplementError` that names the setting, the model is not asked, and no git command and no GitHub request runs

#### Scenario: A process that is not the App
- **WHEN** the process does not hold the private key of the GitHub App
- **THEN** `apply_implement` raises `RoadmapImplementError` before any step

#### Scenario: run-job
- **WHEN** `devops k8s run-job --template runner -- roadmap implement --item 7` runs with no `--repo`
- **THEN** the command exits 1, names `--repo`, and sends no request

### Requirement: No process of a step lives when the job runs git or gh
A `git` or `gh` child of the job holds the session token in its environment, which a process of the same user can read, and a pod cannot hide it (see design.md). So the job SHALL adopt orphans (`PR_SET_CHILD_SUBREAPER`) and, when a step ends, kill every descendant, also one in a session of its own, before it runs any program. A descendant that survives SHALL raise `RoadmapImplementError` and stop the item.

#### Scenario: A daemon of the shell
- **WHEN** a step leaves a process in a session of its own and the step ends
- **THEN** the process is dead before the first `git` of the job runs after the step

#### Scenario: A process that does not die
- **WHEN** a descendant is still alive after the timeout
- **THEN** `RoadmapImplementError` names it

### Requirement: The Job is recorded before it is created
The round SHALL record the name of the Job in `implement.job` and the digest of the runner image in the template of CronJob `devops-cli-runner` in `implement.job_digest`, and clear `implement.job_state`, before it creates the Job. The round SHALL read the CronJob one time for each create, and take the digest and the Job from that read. A create that fails SHALL remove the record of the Job. So a Job that no record names does not exist, and an item whose Job dies early is reported and stopped.

#### Scenario: The order
- **WHEN** a round creates the Job for item 1
- **THEN** the record of item 1 holds the name and the digest when the API receives the create

#### Scenario: A refused create
- **WHEN** the API refuses the create
- **THEN** the round raises `ClusterJobError` and the record of the item holds no Job

### Requirement: A Planned item gets a new branch
For a Planned item the job SHALL make the branch `<type>/<issue>-<slug>` at `origin/<default branch>`. The type is the Conventional Commit type of the title of the item, and the slug is the one of the change folder. The job SHALL run the groups that have an unticked task, regenerate the documentation and archive the change, as it does for a Staged item.

#### Scenario: Two groups
- **WHEN** a Planned item has a change with two unticked groups on `origin/main`, both steps pass, and the checks pass
- **THEN** `origin` holds the new branch with one commit for each group, one for the documentation and one for the archive, GitHub received one draft pull request and one body that starts with `Closes #<issue>`, `gh pr ready` ran once, the record holds `implement.branch` and `implement.pr`, and the Status is In Review

#### Scenario: A group that is done
- **WHEN** every task of group 1 is ticked on `origin/main`
- **THEN** the job runs a step for group 2 only

### Requirement: A Planned item gets a draft pull request at its first push
The job SHALL push the branch of a Planned item with `-u origin` when it first holds a commit past the default branch, and SHALL open a draft pull request into the default branch at once. The first body SHALL hold the closing keyword of the delivered issue once (`Closes #<issue>`) and no other closing keyword, so a stop leaves a grounded draft. The job SHALL record the branch and the pull request, and then go on as it does for a Staged item. A stop before the first commit SHALL push nothing.

#### Scenario: A stop in the first group
- **WHEN** the step of group 1 reports stopped before any commit
- **THEN** `origin` holds no branch for the item, no pull request opened, the Status is Blocked, and `implement.stopped` is `group 1`

#### Scenario: A stop in the second group
- **WHEN** the step of group 2 reports stopped after group 1 passed
- **THEN** `origin` holds the new branch with the commit of group 1, a draft pull request is open with a body that holds `Closes #<issue>` once, the job writes no later body to it, and the record holds its number

#### Scenario: A retry
- **WHEN** a comment `implement: retry` follows that stop
- **THEN** the plan selects the item with the recorded branch and pull request as a Staged item, and the run takes the branch over

#### Scenario: A draft that GitHub refuses
- **WHEN** GitHub refuses the draft pull request after the push
- **THEN** the job removes the branch from `origin`, stops the item, and the record holds no pull request

### Requirement: The pull request that delivers the code has the type of the issue
The job SHALL set the title of the pull request, for a Staged item and for a Planned item, to the type and the scope of the title of the issue and its whole summary. Before it writes the title, the job SHALL check it with the form of the pull request and SHALL stop the item when the form refuses it. The job SHALL leave out the scope when `.github/labels.yml` on the default branch declares no label `scope/<scope>`. The job SHALL set the title in the same call that sets the body `Closes #<issue>`.

#### Scenario: A Staged item
- **WHEN** the staging pull request of a bug has the title `docs(openspec): plan #1 keep every comment` and the job finishes the change
- **THEN** the title of the pull request becomes `fix(roadmap): the job drops a comment`, the title of the issue

#### Scenario: A summary at the limit
- **WHEN** the summary of the title of the issue is 60 UTF-16 code units
- **THEN** the form accepts the title, and the job writes it unchanged

#### Scenario: A long summary
- **WHEN** the summary of the title of the issue is 61 UTF-16 code units
- **THEN** the job stops the item, and the title of the pull request is not written

#### Scenario: A summary of emoji over the limit
- **WHEN** the summary of the title of the issue is 40 emoji of one code point each, which is 80 UTF-16 code units
- **THEN** the job stops the item, and the title of the pull request is not written

#### Scenario: A scope that no label declares
- **WHEN** the title of the issue is `fix(floor): the job drops a comment` and `.github/labels.yml` declares no `scope/floor`
- **THEN** the title of the pull request is `fix: the job drops a comment`

### Requirement: The stop comment of a step holds the diff of the discarded work
When a step stops the item, the comment of the job SHALL also hold the masked diff of the work that the step discarded, in one fenced block, with a note when the diff was cut. The fence SHALL be longer than the longest run of backticks in the diff, and at least three backticks. A stop that is not a step SHALL post no diff.

#### Scenario: A step stops and leaves a diff
- **WHEN** the step of group 1 reports stopped with a diff that holds a token in the form of a GitHub token and a line of three backticks
- **THEN** the comment holds the diff in one fenced block, the fence is four backticks long, the block ends only at the closing fence, the comment holds no token, and the text of the comment after the block is the text of the job

#### Scenario: A cut diff
- **WHEN** the diff of the step was cut
- **THEN** the comment says that the diff is cut to `CONST_ROADMAP_IMPLEMENT_DIFF_CHARS` characters

#### Scenario: A stop that is not a step
- **WHEN** the rebase stops the item
- **THEN** the comment holds no diff

### Requirement: A model-lane round that has not ended does not delay the implement row
The row `implement` SHALL NOT be a row of the model lane. A poll SHALL make it due on the status lane by its interval, whether or not a round of the model lane of the same repository is running. A suspended `implement` row in the ledger of failed rounds SHALL stay suspended on the status lane until the hour ends, and a ledger record that holds an entry of the row SHALL load.

#### Scenario: The model lane is in a long refine round
- **WHEN** the model lane runs a refine round that has not ended, and a poll reaches both lanes of the repository
- **THEN** the status lane runs `metrics` and `implement` while the refine round is still running

#### Scenario: The rows of each lane
- **WHEN** the due table is read
- **THEN** the status lane holds `metrics`, `implement`, `stage_ready` and `release_comments` in this order, and the model lane holds `intake`, `refine`, `stage` and `alternatives`

#### Scenario: A suspended row keeps its suspension
- **WHEN** the record of failed rounds holds an entry of the row `implement` at the limit of rounds, and the status lane runs a round on the same input
- **THEN** the record loads, the row does not run, and the gauge `devops_cli_service_job_suspended` for the row is 1

#### Scenario: A suspended row runs again in a later hour
- **WHEN** the row `implement` failed its limit of rounds in a row, its fault is fixed, and a poll round of a later hour runs on the status lane
- **THEN** the row runs, with no webhook

### Requirement: The job leaves out an item that an agent or a person claimed
The job SHALL take no Item that holds `owner/agent` or `owner/human`, `--item` included, and the plan SHALL give the reason "It is claimed by agent." or "It is claimed by human.". An Item that holds `owner/service` SHALL not be left out for its owner.

#### Scenario: A claimed Staged Item
- **WHEN** a Staged Item that the filter names holds `owner/human`
- **THEN** the plan selects no Item and lists the Item as left out with a reason that contains "claimed by human"

#### Scenario: An agent claimed the named Item
- **WHEN** `--item` names an Item that holds `owner/agent`
- **THEN** the plan lists it as left out with a reason that contains "claimed by agent"

#### Scenario: The Service holds the Item
- **WHEN** a Staged Item holds `owner/service`
- **THEN** the plan selects it

### Requirement: The plan lists the items that matched no filter when asked
`implement --plan` SHALL list, under "Matched no filter" and only with `--why`, each open item that the filter does not name. Each line SHALL name the family that the item misses, the values the filter takes, and the value the item has. The section SHALL not be part of "Left out". Without `--why`, the output SHALL not change.

#### Scenario: Why
- **WHEN** the default filter is in force and a Planned item holds `effort/high`
- **THEN** `implement --plan --why` lists the item under "Matched no filter" with the family `effort`, the values `low or medium`, and the value `high`

#### Scenario: No why
- **WHEN** the same plan runs without `--why`
- **THEN** the output has no section "Matched no filter"

### Requirement: A workstation starts the runner Job for one Item
`devops roadmap implement --item <n> --confirm` with `roadmap.implement.in_runner` false SHALL start the runner Job through the code of `devops k8s run-job --template runner`, with the args `roadmap implement --repo <repo> --item <n> --confirm`. The repository SHALL be `--repo` or the origin of the checkout. The command SHALL follow the log and exit with the exit code of the container, or with `--no-wait` print the name of the Job.

#### Scenario: A Ready Item
- **WHEN** the command runs for a Ready Item of `example/project` with the cluster faked
- **THEN** one Job is created from CronJob `devops-cli-runner` with the args `roadmap implement --repo example/project --item 7 --confirm` and the token repository `example/project`, and the exit code of the container is the exit code of the command

#### Scenario: No wait
- **WHEN** the command runs with `--no-wait`
- **THEN** the Job is created, its name is printed, and the log is not followed

### Requirement: A start from a workstation is refused when it cannot succeed
Before it creates the Job, the command SHALL refuse an Item that an agent or a person claimed, an Item whose Status is neither Ready nor Planned, a closed issue or an issue that is no Item, a repository that is not `owner/name`, and a repository that has a runner Job that has not ended. With `--confirm` it SHALL also refuse `--source`, `--filter`, `--limit` and a missing `--item`, and name the `run-job` command.

#### Scenario: A claimed Item
- **WHEN** the Item holds `owner/human` or `owner/agent`
- **THEN** the command exits 1, names the owner, and creates no Job

#### Scenario: An Item that is not ready to implement
- **WHEN** the Item is New, In Progress, In Review or Blocked, or the issue is closed or is no Item of the roadmap
- **THEN** the command exits 1, names the Status or the cause, and creates no Job

#### Scenario: A running Job
- **WHEN** a Job of the repository carries the label `implement-repo` and has no Complete or Failed condition
- **THEN** the command exits 1, names the Job, and creates no Job

#### Scenario: An option that needs the runner
- **WHEN** the command runs with `--confirm` and `--source`, `--filter` or `--limit`
- **THEN** the command exits 1, names the option and the `run-job` command, and sends no request

#### Scenario: A repository that is no owner and name
- **WHEN** `--repo` is `../..`, `owner/..` or has no slash
- **THEN** the command exits non-zero, reads no Item, and creates no Job

#### Scenario: A step with confirm
- **WHEN** the command runs with `--group` and `--confirm`
- **THEN** the command exits 1, and the message names `devops roadmap implement --item <n> --confirm`

### Requirement: A dry run of the start prints the Job
`devops roadmap implement --item <n> --dry-run` with `roadmap.implement.in_runner` false SHALL make no request and SHALL print the requests of the start, the read of the Item and the Job included. It SHALL ignore `--source`, `--filter` and `--limit`.

#### Scenario: A dry run
- **WHEN** the command runs with `--item 7 --dry-run`
- **THEN** no process starts, no GitHub request is made, and the output names CronJob `devops-cli-runner`, the args of the Job and the read of the Item

#### Scenario: A dry run with an option that needs the runner
- **WHEN** the command runs with `--item 7 --dry-run --limit 2`
- **THEN** the output is the same plan and the command exits 0

### Requirement: A new runner image clears a stop of a retry class
A round SHALL clear the stop of an item that the Service set Blocked, and that no Job and no agent or person holds. The digest in the template of CronJob `devops-cli-runner` must differ from `implement.job_digest`. The class in `implement.failure` must have the action `retry` in `ACTION_BY_CLASS`. A clear SHALL remove `implement.stopped`, set the Status to Ready or Planned, and comment the rule and both digests.

#### Scenario: The digest changed
- **WHEN** an item is Blocked with class `provider` and `implement.job_digest` A and the template names digest B
- **THEN** the round removes `implement.stopped` and sets the Status to Ready
- **AND** the round records the class `provider` and the digest B in `implement.digest_clears` and comments the digest rule with A and B
- **AND** the round creates a Job that records B

#### Scenario: The digest is the same
- **WHEN** an item is Blocked with `implement.job_digest` A and the template names A, no continuation applies, and ten rounds run
- **THEN** the item stays Blocked and the API receives no Job create

#### Scenario: A second stop on the new digest
- **WHEN** the Job that the digest rule started stops the item, no continuation applies, and the template still names B
- **THEN** the item stays Blocked and later rounds create no Job

#### Scenario: A stop with no digest on record
- **WHEN** an item is Blocked with `implement.stopped` and no `implement.job_digest`
- **THEN** the digest rule does not clear it

### Requirement: A clear by digest keeps its record and stays within limits
A clear by digest SHALL append the class, the new digest and the time to `implement.digest_clears`. A stop with no class on record, or with a class of another action, SHALL stay Blocked. The round SHALL NOT clear by digest when the entries for the class reach `roadmap.implement.digest_clears_per_class` (default 1) or the entries of the item reach `roadmap.implement.digest_clears_per_item` (default 3), and SHALL read no content of the runner image.

#### Scenario: A class that a new image cannot fix
- **WHEN** an item is Blocked with class `plan_defect`, `refused_tool`, `premise_false` or `test`, and the template names a new digest
- **THEN** the item stays Blocked, the round reads no template for it, and `implement: retry` still clears it

#### Scenario: A stop with no class
- **WHEN** an item is Blocked with a digest on record and no `implement.failure`, and the template names a new digest
- **THEN** the digest rule does not clear it

#### Scenario: The class limit
- **WHEN** an item is Blocked with class `ci_infra`, `implement.digest_clears` holds one entry of class `ci_infra`, and the template names a new digest
- **THEN** the item stays Blocked until a trusted `implement: retry`

#### Scenario: A second retry class
- **WHEN** an item is Blocked with class `timeout`, `implement.digest_clears` holds one entry of class `provider`, and the template names a new digest
- **THEN** the round clears the stop and the list holds two entries

#### Scenario: The item limit
- **WHEN** an item is Blocked with class `provider`, `implement.digest_clears` holds three entries of other classes, and the template names a new digest
- **THEN** the item stays Blocked until a trusted `implement: retry`

#### Scenario: A record that does not parse
- **WHEN** `implement.digest_clears` is not a valid list
- **THEN** the digest rule does not clear the stop and `implement: retry` still does

### Requirement: A clear by digest writes one comment in a day
The round SHALL write no comment for a clear by digest on an item when `implement.digest_clear_commented_at` is less than 24 hours old, and SHALL still record the clear.

#### Scenario: One clear comment in a day
- **WHEN** a digest clear of an item runs less than 24 hours after `implement.digest_clear_commented_at`
- **THEN** the round clears the stop, records the entry, and writes no comment

#### Scenario: A clear comment after a day
- **WHEN** a digest clear of an item runs 24 hours or more after `implement.digest_clear_commented_at`
- **THEN** the round writes the comment and sets the time to now

### Requirement: A retry from a person clears a stop at once
A comment `implement: retry` of the owner, a member or a collaborator, made after the last comment of the job, SHALL clear the stop of a Blocked item in the next round, whatever the digest. The comment of the Service SHALL name the retry rule.

#### Scenario: A retry on the same digest
- **WHEN** an item is Blocked and its digest is unchanged, and the owner comments `implement: retry`
- **THEN** the round clears the stop, comments the retry rule, and creates a Job

#### Scenario: A retry from a stranger
- **WHEN** a user who is not the owner, a member or a collaborator comments `implement: retry`
- **THEN** the item stays Blocked

### Requirement: The report of a Job names its image digest
The comment that reports a Job that ended SHALL name `implement.job_digest` when the record holds it.

#### Scenario: A Job that failed
- **WHEN** the round reports a Job whose record holds a digest
- **THEN** the comment names that digest

### Requirement: A stop that no rule clears costs one request in each round
The round SHALL list the comments of a Blocked stop one time, and SHALL read the issue again only when a rule holds. It SHALL read the template at most one time, also when the read fails.

#### Scenario: Three stops that nothing clears
- **WHEN** three items are Blocked and no rule clears them
- **THEN** the round sends three listings of comments and reads no issue

### Requirement: The job installs the hook environments before the first step
Before the first step of an item, the job SHALL run `pre-commit install-hooks` in the worktree, outside the agent shell, with `PRE_COMMIT_HOME` under the data directory. A failure SHALL stop the item at the step `hooks` with the output as the reason, before any model request. A repository whose default branch holds no `.pre-commit-config.yaml` SHALL get no install and no `pre-push` check.

#### Scenario: The install fails
- **WHEN** `pre-commit install-hooks` exits 1
- **THEN** no step runs, no model request is made, the item is stopped with the step `hooks`, and the reason holds the output

### Requirement: The job runs the scoped checks before it pushes
After the final rebase and before the push, the job SHALL run, in this order, the `pre-push` stage of the hooks over the commits past the default branch, `devops ci --check --only constructs,docs,openspec`, and `devops ci test` with test modules. It SHALL run each outside the agent shell and without a GitHub token. The job SHALL push a finished item only after all of them pass.

#### Scenario: All checks pass
- **WHEN** an item changes `src/devops_cli/shout.py`, a test module imports it, and every scoped check exits 0
- **THEN** `devops ci test` ran with the path of that test module, the job pushed, and no fix step ran

#### Scenario: A change with no Python file
- **WHEN** the item changes only documents
- **THEN** the job runs no test command, and pushes after the other checks pass

#### Scenario: The pre-push stage runs
- **WHEN** the job runs the scoped checks
- **THEN** one call is `pre-commit run --hook-stage pre-push --from-ref origin/main --to-ref HEAD` in the worktree

### Requirement: The scoped tests check stays small
The test modules of the scoped tests check SHALL be those that the selector of `devops ci test` picks for the changed Python files of `src/` and `tests/`. The job SHALL run no test command when no test covers the change. It SHALL run only the changed test modules when the selection holds more than `CONST_ROADMAP_IMPLEMENT_SCOPED_TEST_MODULES` modules. The comment on the pull request SHALL say so.

#### Scenario: A change that no test covers
- **WHEN** the item changes a source that no test module imports
- **THEN** the job runs no test command, the check is not a failure, and the comment says that no test covers the changed files

#### Scenario: A shared module
- **WHEN** the item changes a module that more than the limit of test modules import, and one test module
- **THEN** `devops ci test` ran with the changed test module only, and the comment says that the others are left to the required checks of CI

### Requirement: Every hook run reads the configuration of the default branch
Every `pre-commit` call of the job SHALL name, with `--config`, a copy of the `.pre-commit-config.yaml` of the default branch, never the file of the checkout. The job SHALL run no hook when the default branch holds none. The copy SHALL leave out a hook whose program the runner image does not hold and that is not on PATH, because no agent can repair a missing program; the checks of the pull request run that hook.

#### Scenario: The agent edits the hook configuration
- **WHEN** the agent writes `repos: []` to `.pre-commit-config.yaml`
- **THEN** every `pre-commit` call names the copy of the configuration of the default branch with `--config`

#### Scenario: A hook whose program is missing
- **WHEN** the default branch configuration holds the hook `devops-ci-workflows-pre-push` and `actionlint` is not on PATH
- **THEN** the copy holds every other hook and not that one

### Requirement: A failed scoped check gets fix steps, and a stop in the phase keeps the work
A failed scoped check SHALL start a fix step with the name and the log of the check. Then the job SHALL generate the documentation again, commit its changes, and run the scoped checks again, at most `roadmap.implement.repair_rounds` times. When no round is left, a fix step stops, an error occurs or a command runs out of time, the job SHALL stop the item and push the commits that passed, as at any other stop. The pull request SHALL stay a draft.

#### Scenario: An ast-grep violation is repaired before the push
- **WHEN** the scoped static check exits 1 with a `pytest.raises` that has no `match`, and the fix step of the stub model adds the `match`
- **THEN** the fix commit is on the branch, the checks run again and pass, and the first push holds the fix

#### Scenario: An error in the scoped checks
- **WHEN** git fails while the job reads the hook configuration after the archive
- **THEN** the item is stopped with the step `scoped checks`, `origin` holds the commits of both groups, and the stop comment names the branch and the last commit

#### Scenario: A hook stage runs out of time in a fix step
- **WHEN** the `pre-commit` stage of a fix step runs out of time
- **THEN** the item is stopped with the step `fix`, the reason says that the command ran out of time, and `origin` holds the commits of both groups

#### Scenario: A check that no fix repairs
- **WHEN** two groups pass, the `pre-push` stage exits 1 after every fix step, and `repair_rounds` is 3
- **THEN** three fix steps ran, `origin` holds the commits of both groups, the item is stopped with the step `scoped checks`, the reason holds the output of the check, the comment names the branch and its last commit, and the job sent no ready request

#### Scenario: A fix step stops
- **WHEN** the fix step of a failed scoped check stops
- **THEN** `origin` holds the commits of both groups, the item is Blocked at the step `fix`, and the comment names the kept work and the action left

#### Scenario: The next Job resumes from the kept work
- **WHEN** a person comments `implement: retry` after a stop in the scoped checks, and the next Job takes the item
- **THEN** the next Job runs no step for a group, runs the scoped checks, and its push holds the commits of the first Job

### Requirement: The comment on the pull request shows the repair rounds and the scoped checks
The comment of the job on the pull request SHALL show a table with one row for each step: the step, its status, its attempts (the first turn and the repair rounds), its tokens in and out and its last failing command. It SHALL show one line for each run of a scoped check with its name, its result and its seconds.

#### Scenario: One repair round
- **WHEN** the step of group 1 used one repair round and the scoped checks passed
- **THEN** the row of group 1 shows 2 attempts, and a line for each scoped check shows `passed` and its seconds

### Requirement: A runner Job starts with a short deadline and an annotation
The Service SHALL create the runner Job with `activeDeadlineSeconds` equal to `roadmap.implement.deadline_extension_seconds` and the annotation `roadmap.devops-cli/progress-at`. A Job that the Service did not annotate SHALL keep its deadline.

#### Scenario: A created Job
- **WHEN** a round creates the Job of an item
- **THEN** the Job spec holds the extension step as `activeDeadlineSeconds` and the annotation holds the time of the create

#### Scenario: A Job without the annotation
- **WHEN** a Job of the repository has no annotation `roadmap.devops-cli/progress-at` and its log changes
- **THEN** the Service patches nothing

### Requirement: A changed log is a progress event
In each round, for each annotated Job of the repository that has not ended and has a start time, the Service SHALL compare the digest of the last lines of its log with the annotation `roadmap.devops-cli/progress`. A digest that differs is a progress event. An empty log, or a log that the API refuses, SHALL NOT be a progress event.

#### Scenario: A log that changed
- **WHEN** the last lines of the log of an annotated Job differ from the lines of the last round
- **THEN** the Service stores the new digest and the time in the annotations

#### Scenario: A log the API refuses
- **WHEN** the API refuses to read the log of an annotated Job
- **THEN** the round raises no error and makes no progress event

#### Scenario: A Job whose pod has not started
- **WHEN** a Job of the repository has no start time
- **THEN** the Service patches nothing

### Requirement: A progress event extends the deadline
On a progress event the Service SHALL set `activeDeadlineSeconds` to the smaller of the ceiling and the greater of the deadline in force and the seconds since the Job started plus the extension step, and SHALL store the digest and the time in the annotations.

#### Scenario: A replay that makes progress for three hours
- **WHEN** the Job log changes before each round for three hours of the faked clock, with the default settings
- **THEN** the Job is not past its deadline at any round, and `activeDeadlineSeconds` is never above the ceiling

#### Scenario: The Job spec shows the deadline
- **WHEN** a round saw progress at 1800 seconds after the Job started, with an extension of 3600
- **THEN** the Job spec holds `activeDeadlineSeconds` 5400

#### Scenario: The deadline stops at the ceiling
- **WHEN** a progress event comes at a time where the start plus the extension is above the ceiling
- **THEN** `activeDeadlineSeconds` equals the ceiling

#### Scenario: The deadline never goes down on progress
- **WHEN** a progress event comes while `activeDeadlineSeconds` is above the start plus the extension
- **THEN** the Job keeps its deadline

### Requirement: A run that makes no progress ends at the stall time
When the log of an annotated Job has not changed for `roadmap.implement.deadline_stall_seconds`, measured from the time in `roadmap.devops-cli/progress-at`, the Service SHALL set `activeDeadlineSeconds` to the seconds since the Job started, set the annotation `roadmap.devops-cli/stalled`, and log the stall. The Job controller then ends the Job. The report comment of a Job that has the annotation SHALL say that the Job stalled and name the stall time.

#### Scenario: A replay that makes none
- **WHEN** the Job log does not change for the stall time and a round runs
- **THEN** the Job spec holds a deadline equal to the seconds since the start, and the annotation `roadmap.devops-cli/stalled` is set

#### Scenario: A silent wait below the stall time
- **WHEN** the Job log does not change for less than the stall time
- **THEN** the Service changes no deadline

#### Scenario: An empty log
- **WHEN** the Job log is empty and the stall time has not passed
- **THEN** the Service changes no deadline

#### Scenario: The report names the stall
- **WHEN** a round reports a Job that ended and has the annotation `roadmap.devops-cli/stalled`
- **THEN** the comment on the item names the stall time

### Requirement: The trace shows each deadline change
Each extension and each stall SHALL be a span `implement.deadline` with the attributes `job`, `deadline.previous_seconds`, `deadline.seconds` and `reason`. The reason SHALL be `progress`, `progress, ceiling` or `stall`. A progress event that changes no deadline SHALL make no span.

#### Scenario: An extension
- **WHEN** a round extends the deadline of a Job
- **THEN** the tracer sends a span `implement.deadline` with the Job name, the old and the new deadline and the reason `progress`

#### Scenario: A stall
- **WHEN** a round ends a Job for a stall
- **THEN** the tracer sends a span `implement.deadline` with the reason `stall`

### Requirement: The extension, the stall and the ceiling are settings
The settings `roadmap.implement.deadline_stall_seconds` (default 4200), `roadmap.implement.deadline_extension_seconds` (default 5400) and `roadmap.implement.deadline_ceiling_seconds` (default 14400) SHALL set the stall time, the extension step and the ceiling, and each SHALL have an environment variable. The configuration SHALL refuse a stall above the extension, an extension above the ceiling, and a ceiling above 14400.

#### Scenario: The defaults
- **WHEN** the configuration is loaded with no value for the three settings
- **THEN** they are 4200, 5400 and 14400

#### Scenario: A stall above the extension
- **WHEN** the stall is set above the extension
- **THEN** the configuration is refused

#### Scenario: A ceiling above the cap
- **WHEN** the ceiling is set to 14401
- **THEN** the configuration is refused

### Requirement: The default stall covers the silent waits of the runner
The default stall SHALL be at least 600 seconds above the longest wait in which the runner writes no log line, and the default extension SHALL be at least the stall plus the interval of the `implement` row plus the interval of a tick of the Service.

#### Scenario: The defaults cover the silent waits
- **WHEN** a test reads the constants of the runner
- **THEN** the default stall is at least the longest of the command timeout, the model call timeout and the monitor timeout plus 600 seconds, and the default extension is at least the stall plus the interval of the row and the tick of the Service

### Requirement: The memory limit of a runner Job stays 8 Gi
The runner Job that the Service creates SHALL have the memory limit of the setting `roadmap.implement.max_memory_limit`, whose default is 8Gi, whatever the deadline settings and the size of the plan are.

#### Scenario: The memory limit
- **WHEN** a round creates a Job and the setting is not set
- **THEN** the memory limit of its container is 8Gi

#### Scenario: A raised limit
- **WHEN** the setting is 12Gi and a round creates a Job
- **THEN** the memory limit of its container is 12Gi

### Requirement: The stop comment names the failure class
The stop comment of the job SHALL name the failure class, the action taken and the action left, before the reason. The job SHALL record the class in `implement.failure` with `implement.stopped`, and SHALL write one line with the class and the action left to its log. A retry of a person and a clear rule of the Service SHALL remove `implement.failure` with `implement.stopped`.

#### Scenario: A step that changed no file
- **WHEN** the step of group 2 stops with the reason "The agent changed no file."
- **THEN** the comment holds `Failure class: `plan_defect`.`, `Action taken: none.` and the action left `amend`, `implement.failure` is `plan_defect`, and the log of the job holds the class and `amend`

#### Scenario: Fix rounds that did not pass a check
- **WHEN** the scoped check `pre-push` fails after 3 fix rounds and its log names `ruff`
- **THEN** the comment holds the class `lint`, the action taken `repair` with 3 rounds, and the action left `wait`

#### Scenario: A retry
- **WHEN** a trusted person comments `implement: retry` on a stopped item and the job takes it
- **THEN** `implement.failure` is removed with `implement.stopped`

### Requirement: The Service counts the failures by class
When a round reports a Job that left a stop, the Service SHALL add 1 to `devops_cli_service_implement_failures_total` with the labels `class` and `repo`, where `repo` is the repository of the round. A Job that left the item without a result SHALL get the class of the tail of its log, recorded in `implement.failure` and named, with the action left, in the report. A Job that ended with a result SHALL add nothing.

#### Scenario: A stop of the runner
- **WHEN** a round of `example/app` reports a Job whose item holds the stop with the class `parser`
- **THEN** the counter for `parser` and `example/app` grows by 1, the counter for `oom` does not change, and a second round adds nothing

#### Scenario: A Job with no result
- **WHEN** a round of `example/app` reports a Job that failed and left the item In Progress, and its log holds "out of memory"
- **THEN** the item is Blocked with `implement.failure` `oom`, the report names the class and the action left `raise_limit`, and the counter for `oom` and `example/app` grows by 1

#### Scenario: A Job with a result
- **WHEN** a round reports a Job that succeeded and left the item In Review
- **THEN** no counter changes

### Requirement: The watch reads check runs and no commit status
The implement job watch SHALL judge the checks of its pull request head from the check runs and SHALL NOT send a request to the commit status endpoint, so a token without the `statuses` permission reads the checks. `devops pr monitor`, `devops pr ready` and `devops pr check-readiness` SHALL keep reading the commit statuses.

#### Scenario: The watch reads check runs
- **WHEN** the watch reads a pull request head whose one check run passed
- **THEN** the watch finds every check passed, and no request goes to the commit status endpoint

#### Scenario: The commit status endpoint refuses
- **WHEN** the commit status endpoint answers HTTP 403 and the check runs of the head passed
- **THEN** the watch finds every check passed, and the item does not stop for unread checks

#### Scenario: A check run fails
- **WHEN** a check run of the head failed
- **THEN** the watch reports that check as failed, and no request goes to the commit status endpoint

#### Scenario: A person's monitor reads the statuses
- **WHEN** `devops pr monitor` reads a head whose commit status endpoint answers HTTP 500
- **THEN** it exits 1

### Requirement: One function decides when a draft pull request is ready
`draft_readiness` SHALL take a draft pull request, its kind (stage plan, implement, agent or person), its recorded item, its check runs and its change folder, and SHALL answer ready, wait or refuse with a reason. A stage plan is complete when opened. An implement pull request is complete when every task group is ticked and the change is archived. An agent's or a person's pull request is complete when its author says so. A failed or unread check refuses, and a running check waits.

#### Scenario: An incomplete implement pull request is refused
- **WHEN** the function reads a pull request of kind implement whose change has one unticked task group
- **THEN** it answers refuse and the reason names that group

#### Scenario: A complete plan with passing checks is ready
- **WHEN** the function reads a pull request of kind stage plan whose check runs all passed
- **THEN** it answers ready

#### Scenario: An author's pull request waits for the author
- **WHEN** the function reads a pull request of kind person or agent whose author has not said that it is complete
- **THEN** it answers wait

#### Scenario: Checks decide after completeness
- **WHEN** the function reads a complete pull request with one failed check, and another with one running check
- **THEN** it answers refuse for the first and wait for the second

#### Scenario: An extra check can refuse
- **WHEN** a test gives the function an extra check that refuses
- **THEN** it answers refuse with the reason of that check, even for a complete pull request with passing checks

### Requirement: The kind of a pull request comes from the record of its item
The kind SHALL come from the item that the head branch `<type>/<issue>-<slug>` names. The claim `owner/agent` SHALL give agent and `owner/human` SHALL give person. Else `implement.pr` equal to the pull request SHALL give implement, and `stage.pr` equal to it SHALL give stage plan. A pull request with no such item SHALL be a person's.

#### Scenario: The four kinds
- **WHEN** four items hold `implement.pr`, the claim `owner/agent`, `stage.pr` and no record of the pull request
- **THEN** their kinds are implement, agent, stage plan and person

#### Scenario: A claim beats the record
- **WHEN** an item holds `stage.pr` of the pull request and the claim `owner/agent`
- **THEN** the kind is agent

#### Scenario: A branch with no issue
- **WHEN** the head branch is `release-please--branches--main`
- **THEN** no item is read and the kind is person

### Requirement: The pull request gets the labels of the new title
For each pull request, after the job sets the title and the body, it SHALL add the `type/*` and `scope/*` labels that the new title gives, as `.github/labels.yml` on the default branch declares them. It SHALL remove each such label that the pull request holds, that the old title gave and that the new title does not give. A label of a person SHALL stay. A label that fails SHALL be named in a comment on the pull request and SHALL NOT stop the item. Rejected credentials SHALL stop it.

#### Scenario: A Staged item changes type and scope
- **WHEN** the pull request holds `type/docs` and `scope/openspec` for the title `docs(openspec): plan #1 keep every comment` and the job sets `fix(roadmap): the job drops a comment`
- **THEN** the pull request holds `type/bug` and `scope/roadmap` and holds neither `type/docs` nor `scope/openspec`

#### Scenario: The labels of the old title are not held
- **WHEN** the pull request holds no label and the job sets a new title
- **THEN** the pull request holds the labels of the new title, and the job sent no request that removes a label

#### Scenario: A label of a person stays
- **WHEN** a person added `scope/ai` to the pull request and neither title gives it
- **THEN** the pull request still holds `scope/ai`

#### Scenario: A Planned item
- **WHEN** the job opens the draft of a Planned item with the title `fix(roadmap): the job drops a comment`
- **THEN** the pull request holds `type/bug` and `scope/roadmap`, and the job sent no request that removes a label

#### Scenario: A label is refused
- **WHEN** GitHub refuses `type/bug` for the pull request
- **THEN** a comment on the pull request names `type/bug` and the reason, and the job watches the checks and marks the pull request ready as it does without the failure

#### Scenario: A dry run
- **WHEN** `devops roadmap implement --dry-run` runs
- **THEN** the plan lists the read of the pull request, the read of `.github/labels.yml`, the request that adds a label and the request that removes one, and the run makes no request

### Requirement: The job keeps the trace of its run
The job SHALL clear `implement.trace` when a run starts, and SHALL write it with each record of a passed group, with a stop and with the ready mark. The value SHALL be JSON with the events and the count `dropped`. When the value is longer than `CONST_ROADMAP_IMPLEMENT_TRACE_CHARS` characters, the job SHALL drop the oldest events and count them in `dropped`.

#### Scenario: A trace that is too long
- **WHEN** a run makes more events than fit in `CONST_ROADMAP_IMPLEMENT_TRACE_CHARS` characters
- **THEN** the value is not longer than the bound, it holds the newest events whole, and `dropped` counts the others

#### Scenario: A new run
- **WHEN** a person retries a stopped item
- **THEN** the job clears `implement.trace` before its first step, and the record holds only the events of the new run

#### Scenario: A Job that ends after a group
- **WHEN** the Service ends a Job after the record of group 1 and before the stop
- **THEN** the record holds the events of group 1

### Requirement: The stop comment shows a table of the steps
The stop comment SHALL hold the table of the comment on the pull request, after the lines of the failure class and before the reason. The row of the step that stopped SHALL be in it. The last failing command SHALL be the command of the last `check` event with an exit status other than 0, or the name of the check of the pull request that failed.

#### Scenario: A step that stops on a failed command
- **WHEN** group 2 stops after one repair round, with 4,100 input and 320 output tokens, and `mypy` exited 1
- **THEN** the table holds the row `group 2`, 2 attempts, `4100/320` and the `mypy` command

#### Scenario: A failed check of the pull request
- **WHEN** the checks of the pull request stop the item with the check `Tests & Coverage` failed
- **THEN** the table holds a row for the step of the checks with `Tests & Coverage` as its last failing command

### Requirement: The table cuts its rows and its cells
The table SHALL list at most `CONST_ROADMAP_IMPLEMENT_TABLE_ROWS` rows, the newest, SHALL cut a command to `CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_CHARS` characters, and SHALL escape a `|` in a cell.

#### Scenario: A command with a pipe
- **WHEN** the last failing command holds `a | b`
- **THEN** the row holds `a \| b` in one cell

#### Scenario: More rows than the bound
- **WHEN** a run has more steps than `CONST_ROADMAP_IMPLEMENT_TABLE_ROWS`
- **THEN** the table holds the newest rows only

### Requirement: A request of a stopped step is judged before the item stops
When a step stops and its last message holds a request (`roadmap-plan-amendment`), the job SHALL judge the request before it stops the item. It SHALL commit an applied amendment as `docs(openspec): amend the plan of group <n> (#N)`, read `tasks.md` again, and run the same group again. It SHALL apply one amendment for each group. A plan that fails the check of the selection is left out before the run, so no request amends a missing test path or a refused command.

#### Scenario: A wrong test path in the plan
- **WHEN** group 1 names a test path that is no file
- **THEN** the plan leaves the item out before the run with the path as its reason, so no step runs and no amendment is committed

#### Scenario: A second request for the same group
- **WHEN** the second step of group 1 stops with another valid request
- **THEN** the job applies nothing, the item is Blocked, and the comment quotes the request as a question

#### Scenario: A stop with no request
- **WHEN** a step stops and its last message holds no `plan-request` block
- **THEN** the job stops the item as it does for any stop

### Requirement: A stop after an amendment names the action taken
When the job applied an amendment for the group that stops the item with the class `plan_defect`, the stop comment SHALL name `amend` as the action taken and `wait` as the action left.

#### Scenario: The amended group fails again
- **WHEN** the job applied an amendment to group 1, and the step of group 1 stops with "The agent changed no file."
- **THEN** the comment holds the class `plan_defect`, the action taken `amend` and the action left `wait`

### Requirement: The comment on the pull request lists each amendment with its evidence
The comment of the job on the pull request SHALL show one line for each applied amendment and each split: the group, the kind, the defect, the evidence, and the old and the new text. A stopped item whose pull request exists SHALL get the same lines in a comment.

#### Scenario: An amended run
- **WHEN** the job applied an amendment and reaches the ready pull request
- **THEN** the comment on the pull request holds a line with the group, the kind, the defect, the evidence, `old` and `new`

#### Scenario: A stop after an amendment
- **WHEN** the job applied an amendment and a later step stops the item, and the pull request exists
- **THEN** the pull request gets a comment with the line of the amendment

### Requirement: A false premise returns the item to New
When a step stops with a `premise` request whose evidence is not empty, the job SHALL return the item to New through `apply_return`, with a comment that holds the evidence masked and cut. It SHALL push nothing, SHALL remove its worktree, and SHALL clear `implement.group`, `implement.sha`, `implement.branch` and `implement.pr`. It SHALL NOT set `implement.stopped`.

#### Scenario: A false premise on a Planned item
- **WHEN** the first step of a Planned item ends with a `premise` request and evidence
- **THEN** the Status is New, the comment holds the evidence, `origin` has no branch for the item, no worktree is left, and the record has no `implement.stopped`

#### Scenario: A false premise on a Staged item
- **WHEN** the step of group 2 of a Staged item ends with a `premise` request, and group 1 passed in this run
- **THEN** the Status is New, `origin` holds the staged branch at the commit it had before the run, and `implement.group` is cleared

#### Scenario: A premise request with no evidence
- **WHEN** the `premise` request has an empty `evidence`
- **THEN** the item is stopped as a question and its Status is Blocked

### Requirement: A group over the limit of the step is split once for each item
When the inputs of a group measure more than the limit of the step, the job SHALL ask the split step of the stage job for the groups that replace it, once for each item. It SHALL write them in place of the group, number the later groups after them, give the lines of `## Criteria` the new numbers with the same criterion text, add an amendment bullet, commit, and run the new groups. A new group over the limit, or a second group over the limit in the same item, SHALL stop the item.

#### Scenario: A group is split
- **WHEN** group 2 of 3 measures more than the limit and the split reply gives two groups under the limit
- **THEN** `tasks.md` holds four groups, the old group 3 is group 4 with its tasks numbered `4.1` and on, the `## Criteria` lines hold the same criterion texts with the new numbers, and the job runs groups 2, 3 and 4

#### Scenario: A new group is still over the limit
- **WHEN** a group of the reply measures more than the limit
- **THEN** the job changes no file and stops the item with the class `plan_defect`

#### Scenario: A second group over the limit
- **WHEN** a split happened and a later group measures more than the limit
- **THEN** the job asks for no second split and stops the item

### Requirement: The dry run lists the writes of an amendment, a return and a split
The plan of `devops roadmap implement --dry-run` SHALL list the commit of an amendment, the model request of a split, and the comment and the Status of a return, each with the condition under which the run makes it.

#### Scenario: The dry run
- **WHEN** `devops roadmap implement --dry-run --item 7` runs
- **THEN** the write requests hold the amendment commit, the split request and the return, and each shows its condition

### Requirement: The spend itemizes token cost per tier
The implement job SHALL itemize the spend of every step under the tier that served it in `implement.spend`.

#### Scenario: Spend itemized per tier
- **WHEN** two steps ran on tier `devops-coder` and tier `devops-reasoning`
- **THEN** the record of the spend holds the token count for each tier and the aggregate total

### Requirement: A step commit title carries the type and scope of the item
The implement job SHALL build the title of each intermediate implementation step commit from the Conventional Commit type and scope of the item title, the title of the task group and one issue reference.

#### Scenario: Docs item step commit
- **WHEN** The item title starts `docs(security):` and the step title is `Correct the Valkey paragraph in SECURITY.md` for issue 2670.
- **THEN** The step commit title is `docs(security): Correct the Valkey paragraph in SECURITY.md (#2670)`.

#### Scenario: Item title with no Conventional Commit type
- **WHEN** The item title is `Correct the Valkey paragraph` and the step title is `Update SECURITY.md` for issue 2670.
- **THEN** The step commit title is `chore: Update SECURITY.md (#2670)`.

#### Scenario: Fix step of an item with no prefix
- **WHEN** The fix step of an item titled `Make the sample shout` commits the group `Make check Static Analysis pass` for issue 1.
- **THEN** The step commit title is `chore: Make check Static Analysis pass (#1)`.

### Requirement: A step commit title holds the issue reference once
The implement job MUST add the issue reference `(#N)` to an intermediate step commit title exactly once, and MUST NOT add it again when the step title already ends with it.

#### Scenario: Step title already holds the issue reference
- **WHEN** The step title ends with `(#2670)` and the issue number is 2670.
- **THEN** The step commit title holds one `(#2670)` suffix.

### Requirement: The archive commit keeps its docs type
The implement job SHALL keep the title of the archive commit in the form `docs(openspec): archive the change (#N)`, whatever the type and scope of the item.

#### Scenario: Archive commit of a docs item
- **WHEN** The implement job archives the change for issue 2670.
- **THEN** The archive commit title is `docs(openspec): archive the change (#2670)`.

### Requirement: A stop names the failed check and the end of its log
A stop of a fix step, and a stop of the scoped checks, SHALL name the failed check and hold the end of its log, at most `CONST_ROADMAP_IMPLEMENT_CHECK_LOG_CHARS` characters, with secrets masked. The stop comment and the job record (`implement.check`, `implement.check_log`) SHALL hold both. A retry or a clear rule of the Service SHALL remove both with the stop. The table of the comment SHALL show the check name as the last failing command when no command failed.

#### Scenario: A fix step that stops
- **WHEN** the check `Tests & Coverage` of the pull request fails with a log that holds a token, and the fix step changes no file
- **THEN** the comment names `Tests & Coverage`, holds the end of the log with the token masked, the row `fix` of the table shows the check name, and `implement.check` and `implement.check_log` hold the same

#### Scenario: A scoped check that still fails
- **WHEN** the scoped check `pre-push` fails after the last fix round
- **THEN** the comment and the record hold the name `pre-push` and the end of its log

#### Scenario: A retry
- **WHEN** a trusted person comments `implement: retry` and the job takes the item
- **THEN** `implement.check` and `implement.check_log` are removed

### Requirement: The comment puts the failed check first and labels the claim
The stop comment SHALL start, after the step, with the failed check. The failed check is the check that the stop names, or else the last command of the step that did not exit 0. The class lines SHALL follow it, and the reason SHALL follow them. The comment SHALL name the last message of the agent as a claim that no check verified.

#### Scenario: The order of the comment
- **WHEN** a stop has a failed check, a reason and a last message
- **THEN** the failed check comes before the class lines, the class lines come before the reason, and the last message follows a label that says that no check verified it

### Requirement: The report reads the item again
`_report` of the Service SHALL read the item again after it reads the log of the Job and before it decides whether the Job left a stop. A stop that the runner wrote in that time SHALL keep its class, and the Service SHALL write no second class.

#### Scenario: The runner stops while the report reads the log
- **WHEN** the item is In Progress in the listing of the round, and the runner writes its stop with the class `timeout` while the report reads the log of the Job
- **THEN** the record keeps the class `timeout`, the report names `timeout`, and the counter for `timeout` grows by 1

### Requirement: The metric labels are classes of the taxonomy
Each panel and alert rule of `k8s/` that reads `devops_cli_service_implement_failures_total` SHALL match the label `class` only with values of the taxonomy.

#### Scenario: A matcher with an unknown value
- **WHEN** a test reads the files of `k8s/` that name the metric
- **THEN** every value of a `class` matcher in them is a class of the taxonomy

### Requirement: The job runs a project step only where the target declares it
The job SHALL run the docs step and the archive step only when the default branch of the target repository declares the step in `.devops/roadmap.toml` under `[implement.steps]`. The job SHALL read the file from the default branch and SHALL NOT read the checkout. A default branch with no file SHALL declare no step. A file that is not valid SHALL stop the item and run no step.

#### Scenario: A target with no declaration skips the docs step
- **WHEN** the default branch of the target holds no `.devops/roadmap.toml` and the job reaches `_finish_change` or `_scoped_rounds`
- **THEN** the job runs no docs command and the job ends with a pull request

#### Scenario: A target with no declaration skips the archive step
- **WHEN** the default branch of the target holds no `.devops/roadmap.toml` and the job reaches `_finish_change`
- **THEN** the job archives no change folder and does not fail, and the pull request is ready with the change not archived

#### Scenario: An agent edit of the declaration changes no step
- **WHEN** an agent adds or removes the declaration in the checkout and the default branch is unchanged
- **THEN** the job runs the steps that the default branch declares and no other

#### Scenario: A target that declares the steps runs them
- **WHEN** the default branch declares `docs = true` and `archive = true`
- **THEN** the job runs the docs command and archives the change folder

#### Scenario: A declaration that is not valid
- **WHEN** the file on the default branch names a step that does not exist
- **THEN** the job stops the item with the path of the file in the reason and runs no step

### Requirement: The comment of the job names each skipped step
The comment of the job on the pull request SHALL name each step that the job skipped and the file that did not declare it.

#### Scenario: Steps skipped
- **WHEN** the job skips the docs step and the archive step
- **THEN** the comment lists `step docs` and `step archive` as skipped

#### Scenario: Steps run
- **WHEN** the job runs both steps
- **THEN** the comment names no skipped step

### Requirement: The job pushes the work in progress of a step
After each `wip:` commit of a step that leaves a task of the group unticked, the job SHALL push the item branch to `origin` with the push of a stop (a push with a lease, or the publish of a Planned item). A `wip:` commit that ticks the last task SHALL wait for the push of the stop or of the end of the run. A push that fails SHALL NOT stop the step.

#### Scenario: A step is killed after three of five tasks
- **WHEN** a step ticks three of five tasks in three separate tool calls, each verification passes, and the model then fails
- **THEN** `origin` held three `wip:` commits on the item branch before the model failed, and `implement.wip` holds the group, 3 done, 5 tasks and the last commit

#### Scenario: The commit of the last tick waits
- **WHEN** a step ticks all five tasks in five tool calls and the model then fails
- **THEN** `origin` held four `wip:` commits before the model failed, and five after the stop

### Requirement: The job records the work in progress of a step
The job SHALL write `implement.wip` to the job record as JSON with the keys `group`, `done`, `of` and `sha` for a `wip:` commit that it pushes, and at a stop for the last `wip:` commit. When a group passes, the job SHALL remove `implement.wip`.

#### Scenario: A group passes
- **WHEN** a step ends done after a `wip:` commit
- **THEN** the job record holds no `implement.wip`

### Requirement: A second Job resumes from the kept work
The next run of an item SHALL take the branch from `origin` with its `wip:` commits. The step message SHALL show the ticks of the kept tasks, and the step SHALL end done in one commit that holds the kept work.

#### Scenario: A retry after a stop
- **WHEN** a Job stopped after three of five tasks, a person comments `implement: retry`, and the second Job does the fourth and the fifth task
- **THEN** the message of the second step shows three tasks ticked and two unticked, the item reaches a ready pull request, and no commit on the branch has a subject that starts with `wip:`

### Requirement: The stop comment names the kept work
When the branch holds `wip:` commits past the default branch, the stop comment SHALL say how many commits the job kept, the branch on `origin`, and the last commit.

#### Scenario: A stop with kept work
- **WHEN** a step stops with three `wip:` commits on the branch
- **THEN** the comment says that the job kept 3 work-in-progress commits on the branch and names the last commit

### Requirement: The job takes the effort passes in order
The job SHALL run one pass for each value of the setting `roadmap.implement.effort`, in the order of the setting. Each pass SHALL take the items of its effort that the filter names, highest priority first. The first pass that takes an item SHALL supply the run, up to the limit.

#### Scenario: A low-effort item is taken before a medium-effort item
- **WHEN** the store holds a Staged Ready P0 item of medium effort and a Staged Ready P2 item of low effort, and the limit is 1
- **THEN** the plan selects the low-effort item and does not select the medium-effort item

#### Scenario: A medium-effort item is taken when no low-effort item is selectable
- **WHEN** the store holds one Staged Ready item of medium effort and no low-effort item, and the limit is 1
- **THEN** the plan selects the medium-effort item, and the plan names the effort pass `medium` as the fallback

#### Scenario: A high-effort item stays out of the default set
- **WHEN** the store holds one Staged Ready item of high effort and no low-effort or medium-effort item
- **THEN** the plan selects no item

### Requirement: A pass that takes no item lets the next pass run
A pass that takes no item SHALL let the next pass run. The items that an earlier pass left out SHALL keep their reasons.

#### Scenario: A claimed low-effort item lets the fallback pass take a medium-effort item
- **WHEN** an agent claims the only Staged Ready low-effort item, a Staged Ready item of medium effort is free, and the limit is 1
- **THEN** the plan selects the medium-effort item and leaves out the low-effort item with the reason that it is claimed

### Requirement: An explicit effort filter replaces the set
When the filter names `effort`, the job SHALL run one pass with the filter as given, and the setting SHALL not apply.

#### Scenario: An explicit effort filter replaces the set
- **WHEN** the job runs with `--filter effort=high`, and the store holds a Staged Ready item of high effort and a Staged Ready item of low effort
- **THEN** the plan selects the high-effort item only

### Requirement: The effort set is a setting
The setting `roadmap.implement.effort` SHALL hold the ordered effort values of the job, and SHALL default to `low` and then `medium`. Each value SHALL be `low`, `medium` or `high`. The setting SHALL refuse a value that is no effort value, and a value that it holds twice. The refusal SHALL name the value.

#### Scenario: One effort value in the set
- **WHEN** the setting `roadmap.implement.effort` holds `low` only, and the store holds one Staged Ready item of medium effort and no low-effort item
- **THEN** the plan selects no item

#### Scenario: The default set
- **WHEN** no config file or variable sets `roadmap.implement.effort`
- **THEN** the setting is `low` and then `medium`

#### Scenario: An unknown value
- **WHEN** `roadmap.implement.effort` holds `low` and `huge`
- **THEN** the settings load fails with a validation error that names `huge`

#### Scenario: A value held twice
- **WHEN** `roadmap.implement.effort` holds `low` and `low`
- **THEN** the settings load fails with a validation error that names `low`

### Requirement: The run report names the effort pass
The run report of the job SHALL name the effort pass that the run uses. When the pass is not the first value of the set, the report SHALL name it as the fallback pass.

#### Scenario: A run takes a medium-effort item
- **WHEN** the plan selects a medium-effort item because no low-effort item is selectable
- **THEN** the rendered plan states the effort pass `medium` and states that it is the fallback pass

#### Scenario: An explicit effort filter names its pass
- **WHEN** the job runs with `--filter effort=high` and the plan selects a high-effort item
- **THEN** the rendered plan states the effort pass `high` and states no fallback pass

#### Scenario: A round logs the pass of the item it selects
- **WHEN** the Service round creates a Job for a medium-effort item because no low-effort item is selectable
- **THEN** the round log names the effort pass `medium` and states that it is the fallback pass

### Requirement: The example ConfigMap holds the effort setting
The example ConfigMap SHALL hold `roadmap.implement.effort` with its default value.

#### Scenario: A test reads the example ConfigMap
- **WHEN** a test reads `k8s/devops/configmap.example.yaml`
- **THEN** the value of `roadmap.implement.effort` is `low` and then `medium`

### Requirement: A stop site passes a typed class of its cause
Each stop of the job whose cause has a class SHALL pass that class, and the stop comment and `implement.failure` SHALL hold it. The classifier SHALL NOT decide a class that a site passes. The words of the last message of the agent and the words of a task SHALL NOT change a class. A step that changed no file SHALL pass `no_change_in_fix` in a fix step and `plan_defect` in a group step.

#### Scenario: A fix step that changed no file
- **WHEN** a fix step stops with the reason "The agent changed no file." and its last message says "The item is already implemented."
- **THEN** the comment holds the class `no_change_in_fix` and `implement.failure` is `no_change_in_fix`

#### Scenario: A group step that changed no file
- **WHEN** the step of group 2 stops with the reason "The agent changed no file."
- **THEN** the class is `plan_defect`

#### Scenario: A lost test, a moved HEAD and the output cap
- **WHEN** a step stops because the agent removed a test, moved HEAD, or reached the output cap
- **THEN** the classes are `tests_lost`, `head_moved` and `output_cap`

#### Scenario: The tier decision
- **WHEN** a turn ends with an error whose text the classifier reads as `parser`, and a second turn ends with the output cap and a message that holds the words of a parser failure
- **THEN** the step moves to the next tier after the first turn only, and the outcome of the step holds the class `parser` for the first and `output_cap` for the second, the class that the decision read

### Requirement: The job leaves out an item whose plan fails the check
The implement selection SHALL run `check_proposal` on the plan of a Staged or Planned item before it returns a target, and it SHALL leave the item out with the first problem as its reason when the check returns problems. It SHALL run no plan check on a Staged item whose branch head holds the archived change of the issue and no active one, because the job archives a change only after the plan passed the check.

#### Scenario: A Staged item with a placeholder task
- **WHEN** The branch of a Staged item holds a plan with the placeholder task `1.1 x`.
- **THEN** `plan_implement` returns no target for the item and its reason holds the first problem.

#### Scenario: A Planned item with a placeholder task
- **WHEN** The default branch holds the plan of a Planned item with the placeholder task `1.1 x`.
- **THEN** `plan_implement` returns no target and makes no branch for the item.

#### Scenario: A plan that passes the check
- **WHEN** The plan of the item passes every `check_proposal` gate.
- **THEN** `plan_implement` returns the item as a target.

#### Scenario: A plan with two problems
- **WHEN** The plan returns two or more problems and the job leaves the item out.
- **THEN** The reason of the item holds the first problem and no later problem.

#### Scenario: A plan that the reader refuses
- **WHEN** The change folder of the item is missing or holds a file that the reader cannot parse.
- **THEN** `plan_implement` returns no target, makes no branch, and its reason names the read problem.

#### Scenario: A test path that no file holds
- **WHEN** The verification command of group 1 names a test path that the staged commit does not hold and that no group creates.
- **THEN** `plan_implement` returns no target for the item, and its reason names the path, so no run starts to amend the path.

#### Scenario: A branch whose change is archived
- **WHEN** The branch head of a Staged item holds `openspec/changes/archive/<date>-1-<slug>/` and no `openspec/changes/1-*/`, and a person comments `implement: retry` after a stop
- **THEN** `plan_implement` returns the item as a target

### Requirement: The plan check lists the default tree once for each run
The implement selection SHALL list the files of `origin/<default>` one time for a run. It SHALL give that list to the plan check of every item that the run judges.

#### Scenario: A run over two Planned items
- **WHEN** A run judges two Planned items in one call to `plan_implement`.
- **THEN** The run lists the files of `origin/<default>` one time.

### Requirement: The plan check reads the base specs once for each run
The implement selection SHALL read each base spec file of `origin/<default>` one time for a run. It SHALL find the spec files in the one listing of the default tree.

#### Scenario: Two items need the base specs
- **WHEN** A run judges two items whose plans the check compares with the base specs.
- **THEN** The run reads each base spec file of `origin/<default>` one time.

### Requirement: The plan check lists the branch of each Staged item
The implement selection SHALL list the files of the branch of each Staged item that it judges. Each Staged item has its own branch.

#### Scenario: Two Staged items on two branches
- **WHEN** A run judges two Staged items whose branches differ.
- **THEN** The run lists the files of each of the two branches one time, and lists the default branch one time.

### Requirement: The reads of one run give the same selection as a read for each item
The implement selection SHALL return for each item the target or the left-out reason that a run over that item alone returns.

#### Scenario: Three items in one run
- **WHEN** A run judges a Planned item whose plan passes, a Planned item whose plan holds a placeholder task, and a Staged item whose plan passes.
- **THEN** Each item gets the target or the left-out reason that a run over that item alone gives.

### Requirement: A default tree that git cannot list leaves the items out
The implement selection SHALL leave out a Planned item whose plan check needs the default tree when git cannot list it. The reason of the item SHALL say that its plan cannot be read from git. A failed listing SHALL end no run.

#### Scenario: Git fails to list the default tree
- **WHEN** A run judges two Planned items and `git ls-tree` of `origin/<default>` fails.
- **THEN** `plan_implement` returns no target, and each item has a left-out reason that says its plan cannot be read from git.

### Requirement: The record keeps the size of the first request of each step
The implement job SHALL record in `implement.spend`, under `steps`, the input tokens of the first model request of each step, from the usage of the first reply of the step. The job SHALL write the figure apart from the trace, so the limit of the trace never drops it.

#### Scenario: A step records its first request
- **WHEN** a step makes two model requests
- **THEN** `implement.spend` holds for that step the input tokens of the first request, and they equal `tokens_in` of the first `model` event of the step.

#### Scenario: A trace over its limit keeps the figure
- **WHEN** a run has more events than `CONST_ROADMAP_IMPLEMENT_TRACE_CHARS` allows
- **THEN** the trace has a `dropped` count above 0, and `implement.spend` still holds the first-request figure of each step.

### Requirement: The job reads the record of a removal from the default branch
The job SHALL give each step the tests that the `## Weakened checks` section of the plan on `origin/<default>` names as `path::name`. The job MUST NOT read that record from the checkout, because the agent can edit the checkout. A plan that is not on the default branch records no test. A section that the plan reader refuses SHALL leave the item out of the plan of a run. When the default branch gets such a section after that plan, the job SHALL stop the item with the class `plan_defect`.

#### Scenario: A merged plan records the removal
- **WHEN** the plan on the default branch names `tests/test_old.py::test_a`, and the step removes that test
- **THEN** the step reports done, and the job goes on to the next group

#### Scenario: The agent writes the record
- **WHEN** the plan on the default branch records nothing, and the agent adds an entry to the `proposal.md` of the checkout and removes the test
- **THEN** the item stops with the class `tests_lost` and the action `wait`

#### Scenario: A section in another form at the plan of a run
- **WHEN** the section on the default branch holds a line that the plan reader refuses
- **THEN** the plan leaves the item out, and the reason holds the line

#### Scenario: A section in another form after the plan of a run
- **WHEN** the default branch gets such a line after the plan selected the item
- **THEN** the item stops with the class `plan_defect` before the step calls the model

### Requirement: The Service continues a Job that ended without a result
A round SHALL clear the stop of an item with the rule `continue` when `implement.stopped` is `job`, the class in `implement.failure` has the action `retry` in `ACTION_BY_CLASS`, and `implement.continuations` is less than `roadmap.implement.continuations_per_item`. A clear SHALL remove `implement.stopped`, `implement.failure` and the failed check, and set the Status to Ready or Planned.

#### Scenario: A Job that was killed
- **WHEN** the Job of an item ended Failed with no result, its log shows no known cause, and `implement.continuations` is not set
- **THEN** the round reports the Job and sets `implement.stopped` to `job` and the class to `ci_infra`
- **AND** the round clears the stop by the rule `continue` and makes a new Job for the same item that takes the branch from `origin`

#### Scenario: A Job that the Service ended by its stall
- **WHEN** the Service ended a Job by its stall and the report gives the class `timeout`
- **THEN** the round continues the item

#### Scenario: A Job that no longer exists
- **WHEN** the record of an item names a Job that the API does not list
- **THEN** the round reports the state `gone` and continues the item

#### Scenario: A class that a new attempt cannot fix
- **WHEN** the log of the Job that ended with no result shows an out-of-memory kill, so the class is `oom` with the action `raise_limit`
- **THEN** the item stays Blocked, `implement.continuations` is not set, and the API receives no Job create until a comment `implement: retry`

#### Scenario: An out-of-memory kill that the log does not show
- **WHEN** a Job ends with no result and its log holds no sign of a memory limit
- **THEN** the class is `ci_infra` and the round continues the item, because the Service reads no pod status

#### Scenario: A stop that the runner wrote
- **WHEN** an item is Blocked with `implement.stopped` as `group 1` and the class `provider`
- **THEN** the rule `continue` does not clear it

### Requirement: The continuations of an item are a setting
The setting `roadmap.implement.continuations_per_item` SHALL default to 2, SHALL refuse a count below 0, and SHALL turn the rule `continue` off at 0.

#### Scenario: The default
- **WHEN** no config file and no variable set the value
- **THEN** `roadmap.implement.continuations_per_item` is 2

#### Scenario: The limit is 0
- **WHEN** `roadmap.implement.continuations_per_item` is 0 and the Job of an item ends with no result
- **THEN** the item stays Blocked and the API receives no Job create

#### Scenario: A negative count
- **WHEN** the variable `DEVOPS_CLI_ROADMAP_IMPLEMENT_CONTINUATIONS_PER_ITEM` is -1
- **THEN** the load of the settings fails with an error that says the value must be greater than or equal to 0

### Requirement: A continuation is counted
A continuation SHALL set `implement.continuations` to the old count plus 1. The record SHALL hold a count and no other data. The count SHALL stay after a clear, and a comment `implement: retry` SHALL NOT reset it.

#### Scenario: No continuation is left
- **WHEN** a Job with a continuation count of 2 ends with no result, and ten rounds run
- **THEN** the item stays Blocked with `implement.stopped` as `job` and the API receives no Job create
- **AND** a comment `implement: retry` of the owner still clears the stop

#### Scenario: A new image at the limit
- **WHEN** the continuation count is at the limit and the template names a digest that differs from `implement.job_digest`
- **THEN** the rule `digest` clears the stop within its own limits, and `implement.continuations` is unchanged

#### Scenario: A count that is not a count
- **WHEN** `implement.continuations` holds `two`, `-1` or `1.5`
- **THEN** the rule `continue` does not clear the stop, the round does not fail, and a comment `implement: retry` still clears the stop

### Requirement: The comment of a continuation says how many are used
The comment of a continuation SHALL name the rule, the Job and the class, and SHALL say "continuation n of N". At the last continuation it SHALL also say "No continuation is left".

#### Scenario: The first continuation
- **WHEN** the rule `continue` clears a stop and `implement.continuations` is not set
- **THEN** `implement.continuations` is 1, the comment says "continuation 1 of 2", and the comment does not say "No continuation is left"

#### Scenario: The last continuation
- **WHEN** a Job with a continuation count of 1 ends with no result and its class has the action `retry`
- **THEN** the round records `implement.continuations` as 2, comments "continuation 2 of 2" and "No continuation is left", and makes a new Job

### Requirement: A continuation spends no clear by digest
The rule `continue` SHALL run before the rule `digest`, SHALL read no template and SHALL add no entry to `implement.digest_clears`.

#### Scenario: A continuation and a new image
- **WHEN** a Job ends with no result and the template names a new digest
- **THEN** the round clears the stop by the rule `continue`, `implement.digest_clears` is not set, and the new Job records the new digest in `implement.job_digest`

### Requirement: The report of a Job with no result says what the Service does next
The report of a Job with no result SHALL say that the Service starts a new Job when a retry can fix the class of the stop. It SHALL name the setting `roadmap.implement.continuations_per_item` and the comment `implement: retry`. It SHALL say that a new runner image also clears the stop within its limits.

#### Scenario: A Job that failed
- **WHEN** the round reports a Job that ended Failed and left its item In Progress
- **THEN** the comment names the setting `roadmap.implement.continuations_per_item` and the comment `implement: retry`

### Requirement: The job checks the premise of a behavior group at the branch tip
Before the job runs a behavior group, the job SHALL check each guard or check identifier that a task of the group adds against the branch tip, and SHALL return the item to New with the definition line when the branch tip defines it. The job SHALL read the kind of the group from `TaskGroup.is_behavior` of `src/devops_cli/roadmap/step_files.py`.

#### Scenario: A task adds a guard that the base already runs
- **WHEN** A behavior group task says to add the guard `_delivery_title` and the branch tip defines `_delivery_title`
- **THEN** The job runs no group step, writes no group file, makes no group commit, and comments the definition line with the return to New.

#### Scenario: A task adds a guard that the base lacks
- **WHEN** A behavior group task says to add the guard `_missing_guard` and the branch tip defines no `_missing_guard`
- **THEN** The job runs the group and commits the file that the group writes.

#### Scenario: A group that is not behavior adds a defined name
- **WHEN** A group whose kind is not behavior has a task that says to add the name `_delivery_title`, which the branch tip defines
- **THEN** The job returns no item to New and runs the group.

### Requirement: One shared definition lookup reports a definition at a commit
The stage job and the implement job SHALL use the definition lookup of `src/devops_cli/roadmap/premise.py`: `definition_lines` returns the lines that define an identifier at a commit, and `defines` reports whether that list is not empty.

#### Scenario: Both jobs get the definition lines from one function
- **WHEN** The stage job probes a cited identifier and the implement job checks a task at the same commit
- **THEN** Both jobs get the same definition lines from `definition_lines` of `src/devops_cli/roadmap/premise.py`.

#### Scenario: The check writes nothing
- **WHEN** The implement job checks the tasks of a behavior group at the branch tip
- **THEN** The check runs only read-only git commands and the worktree holds no change.

### Requirement: The Service sizes the runner Job from the plan
The Service SHALL choose the CPU request, the CPU limit and the memory request of a runner Job from the table `RUNNER_SIZES` by the number of files that the plan names: the small row (CPU 1, memory 2Gi) for at most 10 files, and the large row (CPU 4, memory 6Gi) for more. The other values of the template SHALL stay.

#### Scenario: A plan with few files and a plan with many
- **WHEN** a round creates a Job for a plan whose tasks name 3 files, and another round creates a Job for a plan whose tasks name 12 files
- **THEN** the first Job requests 1 CPU and 2Gi, the second requests 4 CPU and 6Gi, and each keeps the `ephemeral-storage` of the template

### Requirement: The files of a plan are the paths in its tasks
The Service SHALL count the distinct file paths in the code spans of `tasks.md`, read at the revision that holds the plan: `origin/<default branch>` for a Planned item and `origin/<branch>` for a Staged item. A change that is archived at that revision SHALL count zero files.

#### Scenario: Paths are counted once
- **WHEN** the tasks name the same file in several tasks, and name commands and settings in code spans
- **THEN** the count holds each file path once and holds no command and no setting

#### Scenario: A Planned item
- **WHEN** the plan of a Planned item is on the default branch and names 11 files
- **THEN** the Job of the item has the large row

### Requirement: The worker count of a runner Job equals its CPU limit
The Service SHALL set `PYTEST_XDIST_AUTO_NUM_WORKERS` of the Job to the CPU limit of the same Job, and the CPU request SHALL equal the CPU limit.

#### Scenario: Every row
- **WHEN** a test reads each row of the table and the Job that the Service creates for it
- **THEN** the CPU request, the CPU limit and the value of `PYTEST_XDIST_AUTO_NUM_WORKERS` are equal

### Requirement: The size table cites its measurements
Each row of `RUNNER_SIZES` SHALL name the measured Job sample and its peak memory, and the memory request of the row SHALL be above that peak.

#### Scenario: The rows
- **WHEN** a test reads the table
- **THEN** each row has a sample name and a peak, and its memory request is above the peak

### Requirement: The memory limit is a setting that holds the largest request
The setting `roadmap.implement.max_memory_limit` SHALL have the default 8Gi and the variable `DEVOPS_CLI_ROADMAP_IMPLEMENT_MAX_MEMORY_LIMIT`. It SHALL be a whole number of Gi, and the configuration SHALL refuse a value below the largest memory request of the table.

#### Scenario: The default
- **WHEN** the configuration is loaded with no value
- **THEN** the setting is 8Gi

#### Scenario: A value below the largest request or in another form
- **WHEN** the setting is 5Gi, 8G or 8192Mi
- **THEN** the configuration is refused

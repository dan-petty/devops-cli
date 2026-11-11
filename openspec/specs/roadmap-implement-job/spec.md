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
After the last group the job SHALL run `uv run devops docs generate --sync-readme` and commit its changes, then `uv run devops openspec archive <change>` and commit its changes, then rebase, run the scoped checks, then push. The job SHALL run each of these outside the agent shell. When one of them fails, the job SHALL drop the files that no commit holds before the push of the stop, so the rebase of that push finds a clean checkout.

#### Scenario: Two groups
- **WHEN** a Staged low-effort P1 bug has a change with two unticked groups, and both steps pass
- **THEN** the branch holds the commit of the stage job, one commit for each group, one commit for the documentation and one commit for the archive, in that order, and `origin` holds the same branch

#### Scenario: An archive that fails after it moved the change folder
- **WHEN** `main` gains a commit, and then the archive moves the change folder and exits 1
- **THEN** the item stops, `origin` holds the commit of the group and the commit of the documentation, and `main` has no commit that the branch on `origin` lacks

### Requirement: The job rewrites the pull request after the push
After the push the job SHALL build the body of the pull request with `build_body` and set it, in this order: the why of the `proposal.md`, the line `Closes #N`, and the line `Change:` with the folder of the change in a code span. The job SHALL NOT cut the why, and SHALL post the outcome of each step as one comment on the pull request, and put nothing of it in the body.

#### Scenario: The body
- **WHEN** the job finishes the change of item 7
- **THEN** the body of the pull request starts with the why of the proposal, holds `Closes #7` before the `Change:` line, and ends with the `Change:` line of the archive folder, and `body_problems` finds no problem

#### Scenario: A project with no archive step
- **WHEN** the project declares no archive step, so the change folder stays active
- **THEN** the `Change:` line names `openspec/changes/<change>/`

#### Scenario: A long why is not cut
- **WHEN** the Why of the archived proposal is longer than the room that the 1,000 characters of the body leave
- **THEN** the body holds the title of the issue as its why, and holds no `...`

#### Scenario: A why that closes an issue
- **WHEN** the Why holds a closing keyword for an issue, or the proposal has no Why
- **THEN** the body holds the title of the issue as its why

#### Scenario: A refused body stops the item
- **WHEN** `build_body` refuses the body, for a title of the issue that is a placeholder
- **THEN** the job stops the item at the step `pull request`, makes no `PATCH` of the pull request, and the stop comment names the problem

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
The job SHALL keep `implement.group` (the last group that passed), `implement.sha` (the commit it ended on), `implement.branch` (the branch of the pull request), `implement.pr` (the pull request), `implement.base`, `implement.checked_sha`, `implement.published_sha`, `implement.stopped`, `implement.result`, `implement.spend` and `implement.trace` in the job record of the item. The spend SHALL be the requests, input tokens and output tokens of every step that the Jobs of the item ran.

#### Scenario: Spend
- **WHEN** two steps used 3 and 4 requests
- **THEN** the record of the spend holds 7 requests

#### Scenario: The branch
- **WHEN** the job takes a Staged item and a Planned item to a ready pull request
- **THEN** the record of each holds its branch and its pull request

#### Scenario: The trace
- **WHEN** the job takes an item to a ready pull request
- **THEN** the record holds `implement.trace` with the events of the steps, the scoped checks and the commands of the job

#### Scenario: A record of an older version
- **WHEN** the record of an item holds no `implement.result`
- **THEN** the record loads with the key absent and every other key unchanged

### Requirement: The job record keeps the base that a withdraw restores
The job SHALL write `implement.base` once, in the write that sets the Status In Progress, and keep an existing value. The value SHALL be the sha of `origin/<branch>` for a Staged item and `new` for a Planned item. The job SHALL clear `implement.base` when it marks the pull request ready and when it returns the item to New.

#### Scenario: The base of a Staged item and of a Planned item
- **WHEN** the job starts a Staged item and a Planned item
- **THEN** the record of the Staged item holds the sha of its branch on `origin`, and the record of the Planned item holds `new`

#### Scenario: The base is kept by a second Job and cleared at ready
- **WHEN** a first Job is killed after two groups, a second Job takes the item, and the second Job marks the pull request ready
- **THEN** the second Job sees the base of the first Job, and the record holds no `implement.base` after the ready mark

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
When a reported Job leaves its item neither In Review nor stopped, and the record holds no `implement.result` of `ready`, `yielded` or `returned`, the round SHALL set the item Blocked and record `implement.stopped` as `job`. No Job SHALL be created for the item before a clear rule runs.

#### Scenario: A Job that failed
- **WHEN** the Job of an item has the condition Failed, the item is In Progress, the record holds no `implement.result`, and no continuation applies to it
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
- **THEN** the status lane holds `metrics`, `implement`, `stage_ready`, `release_comments`, `github_status` and `cloudflare_status` in this order, and the model lane holds `intake`, `refine`, `stage` and `alternatives`

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
After the final rebase and before the push, the job SHALL run, in this order, the `pre-push` stage of the hooks over the commits past the default branch, `devops ci --check --only constructs,docs,openspec`, and `devops ci test` with test modules. It SHALL run each outside the agent shell and without a GitHub token. The job SHALL push a finished item only after all of them pass, except for a checkpoint.

#### Scenario: All checks pass
- **WHEN** an item changes `src/devops_cli/shout.py`, a test module imports it, and every scoped check exits 0
- **THEN** `devops ci test` ran with the path of that test module, the job pushed, and no fix step ran

#### Scenario: A change with no Python file
- **WHEN** the item changes only documents
- **THEN** the job runs no test command, and pushes after the other checks pass

#### Scenario: The pre-push stage runs
- **WHEN** the job runs the scoped checks
- **THEN** one call is `pre-commit run --hook-stage pre-push --from-ref origin/main --to-ref HEAD` in the worktree

#### Scenario: A checkpoint comes before the scoped checks
- **WHEN** group 1 of two groups passes its step, and the job reaches the boundary of group 2
- **THEN** `origin` holds the commit of group 1 before any scoped check runs, and the final push still follows only after the scoped checks pass

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
`draft_readiness` SHALL take a draft pull request, its kind (stage plan, implement, agent or person), its recorded item, its check runs and its change folder, and SHALL answer ready, wait or refuse with a reason. A stage plan is complete when its title summary and its body are not placeholders. An implement pull request is complete when every task group is ticked and the change is archived. An agent's or a person's pull request is complete when its author says so.

#### Scenario: An incomplete implement pull request is refused
- **WHEN** the function reads a pull request of kind implement whose change has one unticked task group
- **THEN** it answers refuse and the reason names that group

#### Scenario: A complete plan with passing checks is ready
- **WHEN** the function reads a pull request of kind stage plan whose title summary and body are not placeholders and whose check runs all passed
- **THEN** it answers ready

#### Scenario: A stage plan with a placeholder title summary is refused
- **WHEN** the function reads a pull request of kind stage plan whose title is `docs(openspec): plan #3321 x` and whose body is not a placeholder
- **THEN** it answers refuse and the reason names a placeholder summary

#### Scenario: A stage plan with a placeholder body is refused
- **WHEN** the function reads a pull request of kind stage plan whose title summary is not a placeholder and whose body is `x`
- **THEN** it answers refuse and the reason names a placeholder body

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
The job SHALL clear `implement.trace` when a run starts, and SHALL write it with each record of a passed group, with a stop and with the ready mark. The value SHALL be JSON with the events and the count `dropped`. When the value is longer than `CONST_ROADMAP_IMPLEMENT_TRACE_CHARS` characters, the job SHALL drop the oldest `model` events first, then the oldest other events, count them in `dropped`, and keep the sums of their tokens, seconds, repair rounds and outcomes.

#### Scenario: A trace that is too long
- **WHEN** a run makes more events than fit in `CONST_ROADMAP_IMPLEMENT_TRACE_CHARS` characters
- **THEN** the value is not longer than the bound, it holds the kept events whole in the order of the run, and `dropped` counts the others

#### Scenario: Many model events and few progress events
- **WHEN** a run records 5 `tool` or `check` events first, then 200 `model` events and an `attempt` event, and the encoded value is longer than the bound
- **THEN** the value holds the 5 `tool` or `check` events, the newest `model` events and the `attempt` event, and `dropped` counts only the dropped `model` events

#### Scenario: Progress events that alone do not fit
- **WHEN** the trace holds 100 `model` events and 10 `tool` events, and only 8 `tool` events fit the bound
- **THEN** the value holds the newest 8 `tool` events and no `model` event, and `dropped` is 102

#### Scenario: A stored trace from before the order of the run
- **WHEN** a stored trace holds its `model` events after the `tool` events of a turn
- **THEN** the trace decodes with no error, and its events keep the stored order

#### Scenario: A new run
- **WHEN** a person retries a stopped item
- **THEN** the job clears `implement.trace` before its first step, and the record holds only the events of the new run

#### Scenario: A Job that ends after a group
- **WHEN** the Service ends a Job after the record of group 1 and before the stop
- **THEN** the record holds the events of group 1

#### Scenario: The sums of dropped events
- **WHEN** the bound drops model events of 2,030,000 tokens and 400 seconds in all, and no attempt event
- **THEN** the value holds `dropped_tokens` 2030000 and `dropped_seconds` 400.0 and no dropped attempt sum, and a value that is decoded and written again holds the same sums

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
When a step stops with a `premise` request whose evidence is not empty, the job SHALL return the item to New through `apply_return`, with a comment that holds the evidence masked and cut. Before it returns the item, it SHALL withdraw the checkpoints that it pushed, as the requirement on the withdraw says. A return SHALL remove the worktree and SHALL clear `implement.group`, `implement.sha`, `implement.branch`, `implement.pr` and `implement.base`. It SHALL NOT set `implement.stopped`.

#### Scenario: A false premise on a Planned item
- **WHEN** the first step of a Planned item ends with a `premise` request and evidence
- **THEN** the Status is New, the comment holds the evidence, `origin` has no branch for the item, no worktree is left, and the record has no `implement.stopped`

#### Scenario: A false premise on a Planned item after a checkpoint
- **WHEN** groups 1 and 2 of a Planned item passed, the checkpoints opened one draft pull request, and the step of group 3 ends with a `premise` request and evidence
- **THEN** the Status is New, `origin` has no branch for the item, the draft pull request is closed, and the record holds no `implement.base`

#### Scenario: A false premise on a Staged item
- **WHEN** the step of group 2 of a Staged item ends with a `premise` request, and group 1 passed in this run
- **THEN** the Status is New, `origin` holds the staged branch at the commit it had before the run, and `implement.group` and `implement.base` are cleared

#### Scenario: A premise request with no evidence
- **WHEN** the `premise` request has an empty `evidence`
- **THEN** the item is stopped as a question and its Status is Blocked

### Requirement: A return withdraws the checkpoints first
Before the job returns an item to New, it SHALL withdraw the checkpoints that it pushed. For a Staged item, the withdraw SHALL push the sha of `implement.base` back to the item branch with a lease on the last tip that the job pushed. For a Planned item, the withdraw SHALL delete the item branch with the same lease and close the recorded draft pull request, and SHALL do nothing when `origin` holds no item branch. A withdraw that fails SHALL stop the item as Blocked and SHALL NOT return it.

#### Scenario: A person pushed after the last checkpoint
- **WHEN** a person pushes to the item branch after a checkpoint, and a `premise` request with evidence follows
- **THEN** the lease of the withdraw fails, the item is Blocked and is not returned, and the push of the person stays on the branch

#### Scenario: A withdraw that fails
- **WHEN** the push of the withdraw fails with an error that is not a failed lease
- **THEN** the item is Blocked and is not returned, and `origin` keeps the checkpoints

#### Scenario: A withdraw after a refused draft
- **WHEN** GitHub refused the draft of a Planned item at its first checkpoint, and a `premise` request with evidence follows
- **THEN** the withdraw finds no branch on `origin` and does nothing, and the Status is New

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
A stop of a fix step, and a stop of the scoped checks, SHALL name the failed check and hold the end of its log, at most `CONST_ROADMAP_IMPLEMENT_CHECK_LOG_CHARS` characters, with secrets masked. The stop comment and the job record (`implement.check`, `implement.check_log`) SHALL hold both. The next Job SHALL remove `implement.check_log` in its first record write. The comment table SHALL show the check name as the last failing command when no command failed.

#### Scenario: A fix step that stops
- **WHEN** the check `Tests & Coverage` of the pull request fails with a log that holds a token, and the fix step changes no file
- **THEN** the comment names `Tests & Coverage`, holds the end of the log with the token masked, the row `fix` of the table shows the check name, and `implement.check` and `implement.check_log` hold the same

#### Scenario: A scoped check that still fails
- **WHEN** the scoped check `pre-push` fails after the last fix round
- **THEN** the comment and the record hold the name `pre-push` and the end of its log

#### Scenario: A retry
- **WHEN** a trusted person comments `implement: retry` and the job takes the item
- **THEN** `implement.check` and `implement.check_log` are removed

#### Scenario: A clear rule keeps the log
- **WHEN** a clear rule of the Service removes the stop of an item
- **THEN** `implement.check` is removed and `implement.check_log` stays

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
After each `wip:` commit of a step that leaves a task of the group unticked, the job SHALL push the item branch to `origin` with the push of a stop (a push with a lease, or the publish of a Planned item). A `wip:` commit that ticks the last task SHALL wait for the next checkpoint, the push of the stop or the push of the end of the run. A push that fails SHALL NOT stop the step.

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
Each stop of the job whose cause has a class SHALL pass that class, and the stop comment and `implement.failure` SHALL hold it. The classifier SHALL NOT decide a class that a site passes. The words of the last message of the agent and the words of a task SHALL NOT change a class. A step that changed no file SHALL pass `no_change_in_fix` in a fix step and `plan_defect` in a group step. A step whose reset of a moved `HEAD` failed SHALL pass `head_moved`.

#### Scenario: A fix step that changed no file
- **WHEN** a fix step stops with the reason "The agent changed no file." and its last message says "The item is already implemented."
- **THEN** the comment holds the class `no_change_in_fix` and `implement.failure` is `no_change_in_fix`

#### Scenario: A group step that changed no file
- **WHEN** the step of group 2 stops with the reason "The agent changed no file."
- **THEN** the class is `plan_defect`

#### Scenario: A lost test, a moved HEAD and the output cap
- **WHEN** a step stops because the agent removed a test, because the reset of a head that the agent moved failed, or because it reached the output cap
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

#### Scenario: The guard premise fails after a checkpoint
- **WHEN** groups 1 and 2 passed and were pushed as checkpoints, and a behavior group 3 adds a guard that the branch tip defines
- **THEN** the job runs no step for group 3, withdraws the checkpoints as for a `premise` request, and returns the item to New

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

### Requirement: A conflict stop names the conflicted files
When a rebase stops the item on a conflict, the job SHALL read the unmerged files with `git diff --name-only --diff-filter=U` before it aborts the rebase. The stop comment SHALL name each file, the job record SHALL hold the files as `implement.conflict`, and the next Job SHALL clear the record in its first record write. The job SHALL mask each path, list at most `CONST_ROADMAP_IMPLEMENT_REASON_PATHS` paths, and state the number of paths that the cut left out.

#### Scenario: A conflict at the start of a run
- **WHEN** the staged branch conflicts with the default branch in a real git repository when the job rebases at the start of the run
- **THEN** the item stops with the class `conflict`, and the comment names each conflicted file

#### Scenario: A conflict before the push
- **WHEN** the default branch gains a change that conflicts with the branch when the job rebases before the push
- **THEN** the item stops with the class `conflict`, and the comment names each conflicted file

#### Scenario: The record holds the files until a retry
- **WHEN** a conflict stops the item, and a person then comments `implement: retry`
- **THEN** `implement.conflict` holds each file after the stop, and holds none after the first record write of the next Job

#### Scenario: A clear rule keeps the files
- **WHEN** a conflict stops the item and a clear rule of the Service removes the stop
- **THEN** `implement.conflict` still holds each file

#### Scenario: A list above the limit
- **WHEN** the conflict holds more files than `CONST_ROADMAP_IMPLEMENT_REASON_PATHS`
- **THEN** the comment names the files up to the limit and states the number of files left out

#### Scenario: A secret in a path
- **WHEN** a conflicted file path holds a token that `mask_secrets` knows
- **THEN** the comment and the record hold the masked path and not the token

### Requirement: Implement job outcome counter
The roadmap Service SHALL increment `devops_cli_service_implement_jobs_total` with the labels `repo`, `item_class` and `result` once for each runner Job that a round reports.

#### Scenario: A reported runner Job counts once
- **WHEN** A round reports a runner Job for repository `owner/repo`, item class `feat` and result `succeeded`.
- **THEN** The series `devops_cli_service_implement_jobs_total{repo="owner/repo",item_class="feat",result="succeeded"}` increases by one.

### Requirement: Repair rounds counter
The roadmap Service SHALL increment `devops_cli_service_implement_repair_rounds_total` with the labels `repo` and `item_class` by the repair-round count of each reported implement step.

#### Scenario: Repair rounds add to the counter
- **WHEN** A reported implement step records two repair rounds for repository `owner/repo` and item class `feat`.
- **THEN** The series `devops_cli_service_implement_repair_rounds_total{repo="owner/repo",item_class="feat"}` increases by two.

### Requirement: Token counter
The roadmap Service SHALL increment `devops_cli_service_implement_tokens_total` with the labels `repo` and `item_class` by the tokens that the reported runner Job spent, and not by the tokens of earlier Jobs of the item.

#### Scenario: Tokens add to the counter
- **WHEN** A reported runner Job for repository `owner/repo` and item class `feat` records 1,000 tokens.
- **THEN** The series `devops_cli_service_implement_tokens_total{repo="owner/repo",item_class="feat"}` increases by 1,000.

### Requirement: Counted spend
The job record holds the spend of all Jobs of the item, so the roadmap Service SHALL keep the counted token total in the job record key `implement.spend_counted`. It SHALL add only the difference between the spend and that total to the token counter, and SHALL write the new total in the same write that records the state of the Job.

#### Scenario: A second Job counts only its own tokens
- **WHEN** The record of an item holds 1,500 tokens when its first Job is reported, and 4,000 tokens (the sum of both Jobs) when its second Job is reported.
- **THEN** The series increases by 1,500 at the first report and by 2,500 at the second, and `implement.spend_counted` holds `1500` and then `4000`.

### Requirement: Counted spend edge cases
A spend below the counted total SHALL count whole once and become the counted total. A record with no `implement.spend_counted` SHALL count its whole spend once.

#### Scenario: A spend below the counted total counts whole
- **WHEN** The record holds 900 tokens in `implement.spend` and `1500` in `implement.spend_counted` when a Job is reported.
- **THEN** The series increases by 900 and `implement.spend_counted` holds `900`.

#### Scenario: A record of an older version counts its spend once
- **WHEN** The record holds 1,500 tokens in `implement.spend` and no `implement.spend_counted` when a Job is reported.
- **THEN** The series increases by 1,500 and `implement.spend_counted` holds `1500`.

#### Scenario: A Job that spent nothing adds nothing
- **WHEN** The record holds 1,500 tokens in both `implement.spend` and `implement.spend_counted` when a Job is reported.
- **THEN** The series does not increase.

### Requirement: Consecutive-failure gauge
The roadmap Service SHALL expose `devops_cli_service_implement_consecutive_failures` with the labels `repo` and `class`, and the gauge SHALL hold the number of stops in a row of that class.

#### Scenario: A stop increments its class gauge
- **WHEN** A reported stop has class `tests` and the gauge for `tests` is 1.
- **THEN** The gauge `devops_cli_service_implement_consecutive_failures{repo="owner/repo",class="tests"}` becomes 2.

### Requirement: Consecutive-failure gauge persists
The roadmap Service SHALL keep the consecutive-failure gauge value in a state record and SHALL report the same value after a restart.

#### Scenario: A restart keeps the gauge value
- **WHEN** A Service stops with `devops_cli_service_implement_consecutive_failures{repo="owner/repo",class="tests"}` at 2 and a new Service starts from the same state record.
- **THEN** The new Service exposes the same gauge value 2.

### Requirement: Different class resets the earlier gauge
The roadmap Service SHALL set the consecutive-failure gauge of a class to zero when a stop of another class follows.

#### Scenario: A different class resets the earlier gauge
- **WHEN** The gauge for class `tests` is 2 and the next reported stop has class `timeout`.
- **THEN** The gauge for `tests` becomes 0 and the gauge for `timeout` becomes 1.

### Requirement: Delivered item resets the earlier gauge
The roadmap Service SHALL set the consecutive-failure gauge of a class to zero when a delivered item follows.

#### Scenario: A delivered item resets the earlier gauge
- **WHEN** The gauge for class `tests` is 2 and a runner Job reports a delivered item.
- **THEN** The gauge for `tests` becomes 0.

### Requirement: Repair rounds in the job record
The roadmap Service SHALL record the integer repair-round count of each implement step in the item job record from `StepOutcome.repair_rounds`.

#### Scenario: A step with repair rounds is recorded
- **WHEN** An implement step ends with two repair rounds.
- **THEN** The item job record holds the integer `2` for the step's repair-round count.

### Requirement: The job checkpoints each passed group on the item branch
At each group boundary, after the claim check and the premise check and before the step of the group, the job SHALL push the item branch with the push of a stop (a push with a lease, or the publish of a Planned item), when a group passed in this run. The end boundary SHALL push nothing: only the final push, which follows the scoped checks, pushes after the last group.

#### Scenario: A runner is killed after two of four groups
- **WHEN** an item has four groups of one task each, and the runner is killed in group 3
- **THEN** `origin` holds the item branch with the commits of groups 1 and 2

#### Scenario: A second Job runs only the groups that are left
- **WHEN** a first Job is killed after two of four groups, and a second Job takes the item
- **THEN** the second Job runs groups 3 and 4 only, and the item reaches ready

#### Scenario: The first boundary pushes nothing
- **WHEN** the job reaches the boundary of group 1
- **THEN** the job makes no checkpoint push

#### Scenario: The end boundary pushes nothing
- **WHEN** all four groups pass
- **THEN** the job made one push at each of the boundaries of groups 2, 3 and 4, and one final push, and no push at the end boundary

### Requirement: A Planned item gets its draft at the first checkpoint
The first checkpoint of a Planned item SHALL publish the branch and open the draft pull request. A later Job SHALL take the branch as a Staged item. GitHub SHALL be asked for the draft once when it refuses it, and the run SHALL make no more checkpoint pushes after the refusal.

#### Scenario: A Planned item is killed after two of four groups
- **WHEN** a Planned item has four groups of one task each, and the runner is killed in group 3
- **THEN** `origin` holds the item branch with the commits of groups 1 and 2, and GitHub received one request to open a draft pull request

#### Scenario: GitHub refuses the draft
- **WHEN** GitHub refuses the draft at the first checkpoint of a Planned item
- **THEN** the job asked for the draft once, `origin` holds no item branch, the run makes no more checkpoint pushes, and the final push stops the item as it does without a checkpoint

### Requirement: A failed checkpoint does not stop the run
A checkpoint push that fails SHALL NOT stop the run. The job SHALL log the failure, SHALL make no more checkpoint pushes in the run, and SHALL still make the final push.

#### Scenario: A checkpoint push fails
- **WHEN** the push at the boundary of group 2 fails
- **THEN** the run goes on, makes no checkpoint push at the boundaries of groups 3 and 4, and makes the final push

### Requirement: The job skips a phase that passed at the same head
The job SHALL write `implement.checked_sha` with the head after the scoped checks pass, and `implement.published_sha` with the head after it pushes the item branch. A job whose head equals `implement.checked_sha` SHALL run no scoped check. A job whose head equals `implement.published_sha` SHALL push nothing. The job SHALL clear both keys when it marks the pull request ready and when it returns the item to New.

#### Scenario: A second Job at a checked head
- **WHEN** a first Job passes the scoped checks, pushes, and stops in the watch of the checks, and a second Job starts at the same head
- **THEN** the second Job runs no scoped check and pushes nothing, and the record holds both keys until the pull request is ready

#### Scenario: A head that moved
- **WHEN** `implement.checked_sha` holds a sha that is not the head
- **THEN** the job runs the scoped checks and writes the new head

### Requirement: The comment of a run carries the marker of the run
The comment of the job on the pull request SHALL start with the marker of the implement job, and its second line SHALL be `<!-- devops roadmap implement run: <job> -->`, where `<job>` is the value of `implement.job`, or `manual` when the record holds none.

#### Scenario: The marker of a runner Job
- **WHEN** the record holds `implement.job` and the job posts its comment
- **THEN** the first line is the marker of the implement job and the second line names the run

#### Scenario: A job with no job record
- **WHEN** the record holds no `implement.job`
- **THEN** the second line of the comment names the run `manual`

### Requirement: The job keeps one comment for each run
The job SHALL read the comments of the pull request once. It SHALL post one comment for its run, and update that comment for each later write, with the table of all steps of the job. It SHALL write no comment when it has no step, amendment, scoped run or skipped step to show. No comment SHALL have the body `-`.

#### Scenario: A repair round
- **WHEN** a check fails, a fix step runs and the check passes
- **THEN** the pull request holds one comment with the marker of the run, updated once, with the rows of the groups and of the fix

#### Scenario: A rerun with no new outcome
- **WHEN** a second Job finds every group ticked and runs no step
- **THEN** the job posts no comment, and the comment of the first Job keeps its table

### Requirement: The spend of a killed Job counts toward the item budget
The job SHALL write `implement.spend` with each passed group. At the start, the job SHALL read the recorded spend and add it to the spend of its own steps, for the item budget and for the spend that a stop or ready writes. A retry that a person asks for SHALL start from zero spend. A return to New SHALL clear `implement.spend`.

#### Scenario: A continuation after a kill
- **WHEN** a Job is killed after group 1 spent 100 input tokens, and the item budget is 150
- **THEN** the second Job stops with the class `limit_reached` after its first request, and the record of a finished item holds the requests and tokens of both Jobs

#### Scenario: A retry of a person
- **WHEN** a person retries a stopped item
- **THEN** the Job starts from zero spend

#### Scenario: A record of an older version
- **WHEN** the record holds `implement.spend` as an earlier version wrote it, and none of the phase marks
- **THEN** the job starts from that spend and runs the scoped checks

### Requirement: The watch of the checks writes a progress line
While the checks of the pull request run, the job SHALL write one log line at each poll after the first: `The checks of pull request #<pull> still run after <seconds> s.`. The poll interval SHALL be the interval of the watch.

#### Scenario: A watch of three intervals
- **WHEN** a check runs for 60 seconds with a poll interval of 30 seconds
- **THEN** the log holds the lines for 30 s and 60 s, and no line when the checks settle at the first poll

### Requirement: The comment and the phase marks cost five requests
A job SHALL send at most 5 requests more than before for the comment and the phase marks: one read of the comments of the pull request, and for each of the two phase marks one read and one write of the item. A repair round SHALL NOT read the comments again.

#### Scenario: A Job that writes both phase marks
- **WHEN** a job takes an item to a ready pull request
- **THEN** it reads the comments once and writes each phase mark once

### Requirement: A pull request answer holds the title and the body
`PullStatus` SHALL hold the `title` and the `body` of the pull request, with empty defaults, and `get_pull_status` SHALL fill them from the answer of the pull request.

#### Scenario: A stage plan draft is read
- **WHEN** `read_draft` reads a stage plan pull status with title `docs(openspec): plan #3321 x` and body `x`
- **THEN** `draft.pull.title` is the title and `draft.pull.body` is the body

### Requirement: The job writes how its run ended
The job SHALL write `implement.result` as the last mark of the write that ends each run of an item. The value SHALL be `ready` for a pull request marked ready, `stopped` for a stop, `yielded` for a claim, and `returned` for a return to New. The job SHALL clear the key in its first record write of a run.

#### Scenario: A run that a claim ended
- **WHEN** a person claims the item while group 1 runs
- **THEN** the record holds `implement.result` equal to `yielded`

#### Scenario: A run that stops
- **WHEN** the scoped checks stop the item
- **THEN** the record holds `implement.result` equal to `stopped`, written after `implement.stopped`

#### Scenario: A stale result
- **WHEN** a new Job starts on an item whose record holds `implement.result` equal to `ready`, and the Job is killed in its first group
- **THEN** the record holds no `implement.result`

### Requirement: The Service clears the result when it records a Job
The Service SHALL clear `implement.result` in the write that records a new Job of an item.

#### Scenario: A Job that dies before its first write
- **WHEN** the record of an item holds `implement.result` equal to `yielded` and a round creates a Job for the item
- **THEN** the record holds `implement.job` and no `implement.result`

### Requirement: The report reads the result of a Job
The round SHALL read `implement.result` when it reports a Job that ended. A Job with the result `ready`, `yielded` or `returned` SHALL cause no stop of the item. A Job with no result SHALL get its stop and its class from the Status of the item and the tail of its log, with `classify_failure`.

#### Scenario: A yielded Job
- **WHEN** the Job of an item ended, the item is In Progress, and the record holds `implement.result` equal to `yielded`
- **THEN** the round records `implement.job_state`, sets no Status, and records no `implement.stopped`

#### Scenario: A Job with no result
- **WHEN** the Job of an item failed, the item is In Progress, the record holds no result, and the log holds an out-of-memory line
- **THEN** the round records the class `oom` and sets the item Blocked

### Requirement: The first step of a run gets the stop of the earlier Job
The job SHALL read `implement.check_log` and `implement.conflict` before its first record write of a run. It SHALL give both to the first step of the run in a section `# The stop of the earlier Job` of the step message, and to no later step. The section SHALL be left out when both are empty. The prompt `roadmap_implement_step.md` SHALL state what the section holds.

#### Scenario: A retry after a failed check
- **WHEN** an item stopped with a recorded check log and recorded conflict files, and a trusted person retries
- **THEN** the message of the first step holds the log and the files, the message of the second step holds neither, and the record holds neither key after the first record write

#### Scenario: A continuation after a clear rule
- **WHEN** a clear rule of the Service removed the stop and a new Job takes the item
- **THEN** the message of the first step holds the recorded log

### Requirement: A retry and a return to New clear the counted spend
The job SHALL clear `implement.spend_counted` in the same write that clears `implement.spend`, at the start of a retry and at a return to New.

#### Scenario: A retry starts the count from zero
- **WHEN** A person retries an item whose record holds `implement.spend_counted`, and the new Job starts.
- **THEN** the record holds no `implement.spend_counted`.

#### Scenario: A return to New clears the count
- **WHEN** The job returns an item to New and its record holds `implement.spend_counted`.
- **THEN** the record holds no `implement.spend_counted`.

### Requirement: Every push holds the default branch
The job SHALL fetch `origin/<default>` before each push of the item branch, and SHALL push a commit that holds it. Between steps and at a stop the job SHALL rebase the checkout. During a step the job SHALL rebase a copy of `HEAD` in a detached worktree and push the tip of the copy with a lease on the remote tip that it has seen, and the checkout MUST stay as it is. A conflict SHALL abort the rebase, go to the log, and leave the push to go on with the head.

#### Scenario: The first push of a Planned item
- **WHEN** `main` gains a commit while the first step runs, and the step commits its first `wip:` commit
- **THEN** `main` has no commit that the branch on `origin` lacks

#### Scenario: A later work-in-progress push
- **WHEN** `main` gains a commit after the first `wip:` push, and the step commits a second `wip:` commit
- **THEN** `main` has no commit that the branch on `origin` lacks

#### Scenario: A checkpoint
- **WHEN** `main` gains a commit while group 2 runs
- **THEN** after the checkpoint of group 2 the branch on `origin` holds that commit

#### Scenario: A stop
- **WHEN** `main` gains a commit and the step stops
- **THEN** the push of the stop holds that commit, and `implement.wip` names the last `wip:` commit of the branch on `origin`

#### Scenario: A conflict during a step
- **WHEN** `main` gains a commit that conflicts with the first `wip:` commit
- **THEN** the push keeps the `wip:` commit on `origin`, the log holds the text of the rebase conflict, and no rebase stays in progress

### Requirement: The comments and the record show the extension of a step budget
The record `implement.spend` SHALL hold, for each step that got the one extension of its token budget, the old budget, the new budget, the counts that gave it and whether the ceiling cut it. The ready comment and the stop comment of the item SHALL list each such step of the run, the earlier Jobs included, with the budgets and the counts only. A run with no extension SHALL show no such list.

#### Scenario: A ready item with an extended step
- **WHEN** group 1 got an extension from 100 to 150 input tokens with 2 successful edits and 0 refused commands, and the item reaches a ready pull request
- **THEN** the ready comment lists group 1 with 100 to 150 input tokens and those counts, and the record holds the extension of group 1 and none for group 2

#### Scenario: A stop after an extension
- **WHEN** group 1 got an extension and then reached its new budget
- **THEN** the stop comment names the class `limit_reached`, lists the extension of group 1 and gives the reason that names the extension

#### Scenario: No extension
- **WHEN** no step of the run got an extension
- **THEN** the comment of the item lists no budget extension

### Requirement: The job leaves out a Staged item whose draft holds the label plan/needs-fix
The implement selection SHALL leave out a Staged item while its open draft pull request holds the label `plan/needs-fix`, with a reason that names the label and the pull request. The row `implement` of the Service SHALL log such an item once for each draft and record the draft in `implement.needs_fix`. The selection SHALL take the item again when the label is gone, and a round that judges the item and does not leave it out for the label SHALL clear the mark.

#### Scenario: The draft holds the label
- **WHEN** the open draft of a Staged item holds the label `plan/needs-fix`
- **THEN** `plan_implement` returns no target for the item, and its reason names the label and the pull request

#### Scenario: The Service logs the item once
- **WHEN** two rounds of the row `implement` judge the item while its draft holds the label
- **THEN** no round creates a Job, the log holds one line for the item, and `implement.needs_fix` holds the number of the draft

#### Scenario: The label is gone
- **WHEN** a round judges the item after the label was removed from its draft
- **THEN** the round creates the Job of the item and clears `implement.needs_fix`

#### Scenario: The label comes back
- **WHEN** the label comes back on the draft after a round judged the item without it
- **THEN** the next round logs the item again and creates no Job

### Requirement: A spec that the archive validation refuses is a plan defect
When `uv run devops openspec archive <change>` exits with status 1 after it moved the change folder into the archive, the strict validation of the specs refused a spec of the plan. The stop SHALL pass the class `plan_defect`, so the action left is `amend`. The words of the output, as `1 failed`, SHALL NOT decide the class. An archive that fails before it moves the folder SHALL keep the class that the classifier gives.

#### Scenario: The validation refuses a long requirement
- **WHEN** the archive moves the change folder, then exits 1 with `Totals: 258 passed, 1 failed (259 items)` and a requirement text longer than 500 characters
- **THEN** the item stops at the archive, `implement.failure` is `plan_defect`, and the comment names the action left `amend` and the spec that failed

#### Scenario: An archive that keeps the change folder
- **WHEN** the archive exits 1 with `openspec: the change has no delta` and the change folder stays in place
- **THEN** the item stops at the archive with the class `ci_infra`

### Requirement: The record keeps the tokens of each step
The implement job SHALL record in `implement.spend`, under `steps`, for each step: its model requests, its input tokens, its output tokens, its repair rounds and the input tokens of its largest model request, from the usage of the replies of the step. The job SHALL write these figures apart from the trace, so the limit of the trace never drops them.

#### Scenario: A step whose requests grow
- **WHEN** the requests of a step report an input that grows with the conversation
- **THEN** the entry of the step holds the count of the `model` events of the step, the sums of their `tokens_in` and `tokens_out`, and their largest `tokens_in`, which is above the first request of the step

#### Scenario: A step with a repair round
- **WHEN** the lint check of group 1 fails once and one repair turn fixes it
- **THEN** the entry of group 1 holds 1 repair round and the 4 requests of both turns

# roadmap-implement-job/pull-request Specification

## Purpose
The branch and the pull request of an implement item: the commits and their titles, the work in progress and the checkpoints, the pushes, the rewrite of the pull request, and the mark as ready.

## Requirements

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

### Requirement: A pull request answer holds the title and the body
`PullStatus` SHALL hold the `title` and the `body` of the pull request, with empty defaults, and `get_pull_status` SHALL fill them from the answer of the pull request.

#### Scenario: A stage plan draft is read
- **WHEN** `read_draft` reads a stage plan pull status with title `docs(openspec): plan #3321 x` and body `x`
- **THEN** `draft.pull.title` is the title and `draft.pull.body` is the body

### Requirement: Every push holds the default branch
The job SHALL fetch `origin/<default>` before each push of the item branch, and SHALL push a commit that holds it. Between steps and at a stop the job SHALL rebase the checkout. During a step the job SHALL rebase a copy of `HEAD` in a detached worktree and push the tip of the copy with a lease on the remote tip that it has seen, and the checkout MUST stay as it is. A conflict SHALL abort the rebase and go to the log, and the job SHALL push nothing.

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
- **WHEN** `main` of a Planned item gains a commit that conflicts with the first `wip:` commit, and the step then stops
- **THEN** `origin` has no item branch, the log holds the text of the rebase conflict, and no rebase stays in progress

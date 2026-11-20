# roadmap-implement-job/pull-request Specification

## Purpose
The branch and the pull request of an implement item: the commits and their titles, the checkpoints, the pushes, the rewrite of the pull request, and the end of the run at the draft.

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
After the last group the job SHALL run `uv run devops docs generate` and commit its changes, then `uv run devops openspec archive <change>` and commit its changes, then rebase, run the scoped checks, then push. The job SHALL run each of these outside the agent shell. When one of them fails, the job SHALL drop the files that no commit holds before the push of the stop, so the rebase of that push finds a clean checkout.

#### Scenario: Two groups
- **WHEN** a Staged low-effort P1 bug has a change with two unticked groups, and both steps pass
- **THEN** the branch holds the commit of the stage job, one commit for each group, one commit for the documentation and one commit for the archive, in that order, and `origin` holds the same branch

#### Scenario: An archive that fails after it moved the change folder
- **WHEN** `main` gains a commit, and then the archive moves the change folder and exits 1
- **THEN** the item stops, `origin` holds the commit of the group and the commit of the documentation, and `main` has no commit that the branch on `origin` lacks

### Requirement: Commit stage runs before docs and archive commits
The job SHALL run the trusted commit stage on the staged changes of each commit that `_commit_if_changed` makes before `git commit`. When a fixer hook rewrites a file, the job SHALL stage the file, run the stage once more, and commit the rewritten file. When the stage fails on the second run, the job SHALL stop the item with the hook output, and make no docs or archive commit. When the commit holds no change, the job SHALL make no commit and run the stage zero times.

#### Scenario: Docs commit runs the stage and fixes whitespace
- **WHEN** the docs generator changes a generated file with trailing whitespace
- **THEN** the commit stage runs over the staged changes before `git commit`, trims the whitespace, and commits the cleaned file

#### Scenario: Hook failure on docs or archive commit stops the item
- **WHEN** the commit stage fails on staged changes and fails again after fixer files are staged
- **THEN** the item stops with the hook output in the stop comment, and no docs or archive commit is made

#### Scenario: Docs generator writes nothing
- **WHEN** the docs generator writes no file and the checkout holds no change
- **THEN** the job makes no commit and runs the commit stage zero times

### Requirement: The job rewrites the pull request after the push
Once the job has finished the change and before it pushes the commits, it SHALL set the title and the body of the pull request, with `build_body` for the body: the why of the `proposal.md`, `Closes #N`, and `Change:` with the change folder in a code span. It SHALL NOT cut the why. One pull request SHALL take one update, so a second call sends no `PATCH` and adds no label again. It SHALL post the outcome of each step as one comment after the push, and put nothing of it in the body.

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
- **WHEN** `build_body` refuses the rebuilt body too
- **THEN** the job stops the item at the step `pull request` with the class `refused_reply`, makes no `PATCH` of the pull request, makes no third model call, and the stop comment names the problems

#### Scenario: The metadata comes before the archived push
- **WHEN** a Staged item archives its change and a scoped check fails before the push
- **THEN** the `PATCH` of the title and the body came before the push of the archived commit, and the pull request holds the delivery title and a body that holds `Closes #1`

#### Scenario: One update for one pull request
- **WHEN** the run calls the metadata write twice for the same pull request
- **THEN** the job sends one `PATCH` and one label write, and the pull request holds each label once

### Requirement: A Planned item gets a new branch
For a Planned item the job SHALL make the branch `<type>/<issue>-<slug>` at `origin/<default branch>`. The type is the Conventional Commit type of the title of the item, and the slug is the one of the change folder. The job SHALL run the groups that have an unticked task, regenerate the documentation and archive the change, as it does for a Staged item.

#### Scenario: Two groups
- **WHEN** a Planned item has a change with two unticked groups on `origin/main`, both steps pass, and the checks pass
- **THEN** `origin` holds the new branch with one commit for each group, one for the documentation and one for the archive, GitHub received one draft pull request and one body that starts with `Closes #<issue>`, `gh pr ready` ran never, `implement.result` is `drafted`, the record holds `implement.branch` and `implement.pr`, and the Status is In Review

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
The job SHALL set the delivery pull request title using the Conventional Commit type selected by the changed paths. The summary SHALL come from the proposal `## Summary` section, `## What Changes`, or the issue summary. Before writing the title, the job SHALL check it with the pull request form and fall back to the issue title when invalid. The job SHALL drop undeclared scopes, and SHALL set the title when setting `Closes #<issue>`.

#### Scenario: A test-only plan
- **WHEN** the staged plan changes only paths under `tests/` and the issue title starts with `perf(roadmap):`
- **THEN** `_delivery_title()` returns a title that starts with `test(roadmap):`

#### Scenario: A proposal with a summary
- **WHEN** the archived proposal has a `## Summary` section whose first line is `pin a single registry read` and the changed paths are test-only
- **THEN** `_delivery_title()` returns `test(roadmap): pin a single registry read`

#### Scenario: A proposal without a summary
- **WHEN** the proposal has no `## Summary` section and its first `## What Changes` bullet is `- Add two regression tests`
- **THEN** `_delivery_title()` returns a title whose summary is `Add two regression tests`

#### Scenario: No usable proposal summary
- **WHEN** the proposal has no `## Summary` and no `## What Changes` section
- **THEN** `_delivery_title()` returns the title that `delivery_title(self.target.item.title, declared)` returns

#### Scenario: A Staged item
- **WHEN** the title of the issue is `fix(roadmap): the job drops a comment`, the commit of the staged branch that adds the change folder has the subject `docs(openspec): plan #1 Keep the last comment of a thread`, and the job finishes the change
- **THEN** the title of the pull request becomes `fix(roadmap): Keep the last comment of a thread`

#### Scenario: An issue that states a goal and a plan that states a smaller change
- **WHEN** the title of issue 3785 is `fix(k8s): find the source of the <gpu-node> host crashes` and its plan commit has the subject `docs(openspec): plan #3785 Remove the profiler exclusion of the <gpu-node> node (#5182)`
- **THEN** the title of the pull request is `fix(k8s): Remove the profiler exclusion of the <gpu-node> node`

#### Scenario: A summary at the limit
- **WHEN** the item has no plan title and the summary of the title of the issue is 60 UTF-16 code units
- **THEN** the form accepts the title, and the job writes it unchanged

#### Scenario: A long summary
- **WHEN** the item has no plan title and the summary of the title of the issue is 61 UTF-16 code units
- **THEN** the job stops the item, and the title of the pull request is not written

#### Scenario: A summary of emoji over the limit
- **WHEN** the item has no plan title and the summary of the title of the issue is 40 emoji of one code point each, which is 80 UTF-16 code units
- **THEN** the job stops the item, and the title of the pull request is not written

#### Scenario: A scope that no label declares
- **WHEN** the title of the issue is `fix(floor): the job drops a comment` and `.github/labels.yml` declares no `scope/floor`
- **THEN** the title of the pull request is `fix: the job drops a comment`

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
- **THEN** a comment on the pull request names `type/bug` and the reason, and the run ends at the draft as it does without the failure

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

### Requirement: The job checkpoints each passed group on the item branch
At each group boundary, after the claim check and the premise check and before the step of the group, the job SHALL push the item branch with the push of a stop (a push with a lease, or the publish of a Planned item), when a group passed in this run. The end boundary SHALL push nothing: only the final push, which follows the scoped checks, pushes after the last group.

#### Scenario: A runner is killed after two of four groups
- **WHEN** an item has four groups of one task each, and the runner is killed in group 3
- **THEN** `origin` holds the item branch with the commits of groups 1 and 2

#### Scenario: A second Job runs only the groups that are left
- **WHEN** a first Job is killed after two of four groups, and a second Job takes the item
- **THEN** the second Job runs groups 3 and 4 only, and the item reaches the draft

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
The job SHALL write `implement.checked_sha` with the head after the scoped checks pass, and `implement.published_sha` with the head after it pushes the item branch. A job whose head equals `implement.checked_sha` SHALL run no scoped check. A job whose head equals `implement.published_sha` SHALL push nothing. The job SHALL clear both keys when the run ends at the draft and when it returns the item to New.

#### Scenario: A second Job at a checked head
- **WHEN** a first Job passes the scoped checks, pushes, and stops before the end of the run, and a second Job starts at the same head
- **THEN** the second Job runs no scoped check and pushes nothing, and the record holds both keys until the run ends at the draft

#### Scenario: A head that moved
- **WHEN** `implement.checked_sha` holds a sha that is not the head
- **THEN** the job runs the scoped checks and writes the new head

### Requirement: A pull request answer holds the title and the body
`PullStatus` SHALL hold the `title` and the `body` of the pull request, with empty defaults, and `get_pull_status` SHALL fill them from the answer of the pull request.

#### Scenario: A stage plan draft is read
- **WHEN** `read_draft` reads a stage plan pull status with title `docs(openspec): plan #3321 x` and body `x`
- **THEN** `draft.pull.title` is the title and `draft.pull.body` is the body

### Requirement: The summary of the delivery title comes from the plan
The summary of the plan SHALL be the text after `docs(openspec): plan #<issue>` and one space in the subject of the newest commit of the branch that adds `proposal.md` to a folder `openspec/changes/<issue>-<slug>/`, without the end `(#<pull>)` that a squash merge adds. The job SHALL use the whole summary of the title of the issue when that subject holds no such text, or when the form of the pull request refuses the title with the summary of the plan.

#### Scenario: A Planned item
- **WHEN** the commit on `main` that adds the change folder of item 1 has the subject `docs(openspec): plan #1 Keep the last comment of a thread (#4)`
- **THEN** the job opens the draft with the title `fix(roadmap): Keep the last comment of a thread`, and writes the same title when it finishes the change

#### Scenario: No plan title
- **WHEN** the commit that adds the change folder has the subject `fix(roadmap): plan` and the title of the issue is `fix(roadmap): the job drops a comment`
- **THEN** the title of the pull request is `fix(roadmap): the job drops a comment`, the title of the issue

#### Scenario: A plan summary that the form refuses
- **WHEN** the summary of the plan has 64 characters, and the title of the issue is `fix(roadmap): the job drops a comment`
- **THEN** the title of the pull request is `fix(roadmap): the job drops a comment`, and the job does not stop the item

### Requirement: A prompt change waits for its live eval scores
`draft_readiness` SHALL refuse a draft whose changed files hold `src/devops_cli/ai/tasks/roadmap_stage_change.md` and whose body holds no number on the last `Base eval score:` line or the last `Head eval score:` line. The reason SHALL name each missing marker. The rule SHALL NOT apply to a draft whose files hold no such path. `read_draft` SHALL pass the compare files of every kind to the draft, and the ready step of the implement job SHALL pass the paths of its local diff.

#### Scenario: A prompt change with no score
- **WHEN** the function reads a complete draft that changes the stage prompt and its body holds no score line
- **THEN** it answers refuse, and the reason names the base score and the head score

#### Scenario: A prompt change with one score
- **WHEN** the body holds a base score and no head score, or a head score and no base score
- **THEN** it answers refuse, and the reason names only the missing score

#### Scenario: A prompt change with both scores
- **WHEN** the body holds `Base eval score: 11` and `Head eval score: 12`
- **THEN** it answers ready

#### Scenario: A repeated marker and a marker with no number
- **WHEN** the body holds two base score lines whose last line has a number, and a head score line with no number
- **THEN** it answers refuse, and the reason names the head score only

#### Scenario: A change without the prompt file
- **WHEN** the changed files hold no stage prompt path and the body holds no score
- **THEN** the score rule answers no reason, and the other rules decide

### Requirement: The option skips the fetch and the rebase
`devops roadmap implement` SHALL accept a `--no-rebase` option that skips the fetch of the default branch and the rebase of the branch before the first step and before the push.

#### Scenario: The option skips both syncs
- **WHEN** a runner Job runs `roadmap implement --repo <owner/name> --item 7 --confirm --no-rebase` in a real repository whose `origin/main` holds a commit that the branch lacks
- **THEN** the worktree gets no `git fetch -q origin main` and no `git rebase` at the start or before the push, the branch keeps its commits, and the job pushes them with the lease

### Requirement: A refused body is rebuilt once
The job SHALL send every problem of a refused pull request body to the model one time, and SHALL rebuild the body from the reply. A rebuilt body that passes `body_problems` SHALL be written to the pull request. A rebuilt body that fails SHALL stop the item with the class `refused_reply`, and the job SHALL make no third model call.

#### Scenario: The first refusal
- **WHEN** `build_body` refuses the body that the job built
- **THEN** the job makes one model call that carries the refused text and every problem, and rebuilds the body from the reply

#### Scenario: The rebuilt body passes
- **WHEN** `body_problems` returns an empty problem list for the rebuilt body
- **THEN** the job writes the rebuilt body to the pull request and continues the step with no stop

#### Scenario: A second refusal
- **WHEN** `build_body` refuses the rebuilt body
- **THEN** the job stops the item with the class `refused_reply` and makes no third model call

### Requirement: The comment of a run names the comments of the item that the steps read
The comment of a run on the pull request SHALL name, by its page, each comment of the item that the inputs of a step of the run held whole, each once, in the order of the steps. A run whose inputs held no comment SHALL have no such line.

#### Scenario: A comment of the item
- **WHEN** the item has one comment with a known page and the run passes two groups
- **THEN** the comment of the run names the page once, on the line "comments of the item in the step inputs"

### Requirement: Type label follows title
The implement job SHALL set the pull request's `type/*` label from the delivery title and remove any stale `type/*` label.

#### Scenario: A test-only plan on a `type/infra` issue
- **WHEN** the implement job updates a pull request whose current title is `perf(roadmap): cache registry_table in stage eval replay` and the delivery title is `test(roadmap): pin a single registry read`
- **THEN** the pull request has `type/test` and does not have `type/infra`

### Requirement: The pull request comment names the tools of the job
The implement job SHALL name each tool that a step called, with its count, in the comment of the Job on the pull request. The line of the tool counts SHALL hold no argument, path or file content.

#### Scenario: The comment names each tool of the job
- **WHEN** A Job ends with two calls of `read_file` and one call of `pr_describe`, and one step of it fails a check whose command names a path.
- **THEN** The comment holds the count of each of the two tools, the line of the counts holds no argument of a tool call and no path, and the table of the steps keeps the failing command with its path.

### Requirement: The run ends at the draft pull request
After the job sets the title and the body of the draft and comments each step, it SHALL ask `draft_readiness` with no check runs, and a refusal SHALL stop the item at the step `ready`. Then it SHALL end the run: it SHALL record `implement.result` as `drafted`, the pull request, the last commit and the spend, set Status to In Review, and comment the spend on the item. The job SHALL NOT watch the checks, publish an evidence comment, run `gh pr ready` or merge.

#### Scenario: The end of a run
- **WHEN** every group passes and the job pushes the branch
- **THEN** the draft holds the final title and body, `gh pr ready` ran never, the record holds `implement.result` equal to `drafted` and the number of the pull request, and Status is In Review

#### Scenario: A draft that the readiness function refuses
- **WHEN** the archive leaves a task of group 2 unticked
- **THEN** the item is Blocked at the step `ready` with the class `plan_defect`, and the record holds no `implement.result` equal to `drafted`

### Requirement: A push rebases the checkout onto the default branch
The job SHALL fetch `origin/<default>` before each push of the item branch, including after the scoped checks of the final push, and SHALL push a commit that holds it. Between steps, after the scoped checks, and at a stop the job SHALL rebase the checkout.

#### Scenario: The first push of a Planned item
- **WHEN** `main` gains a commit while the first step runs, and the step of group 2 then stops
- **THEN** `main` has no commit that the branch on `origin` lacks

#### Scenario: A checkpoint
- **WHEN** `main` gains a commit while group 2 runs
- **THEN** after the checkpoint of group 2 the branch on `origin` holds that commit

#### Scenario: The final push
- **WHEN** `main` gains a commit while the scoped checks run
- **THEN** after the scoped checks the pushed branch on `origin` holds that commit

#### Scenario: A conflict after scoped checks
- **WHEN** `main` gains a conflicting commit while the scoped checks run
- **THEN** the job stops with status Blocked, and the job pushes nothing

#### Scenario: A stop
- **WHEN** `main` gains a commit and the step stops
- **THEN** the push of the stop holds that commit

### Requirement: A conflicting checkpoint or stop push keeps the head on the item branch
A checkpoint or stop push whose rebase conflicts SHALL abort the rebase, push the head of the checkout to the item branch with a lease, and record the conflicting paths in `implement.conflict`. The run SHALL make its next checkpoint push. The final push whose rebase conflicts MUST push nothing, MUST keep the item branch on `origin`, and SHALL stop the item with the class `conflict`, naming the conflicting paths in its comment.

#### Scenario: A conflict at a checkpoint
- **WHEN** `main` gains a commit that changes `CONTEXT.md` after group 1 passed, and the checkpoint push before group 2 conflicts
- **THEN** the checkpoint push before group 3 puts the commit of group 2 on the item branch, and `implement.conflict` names `CONTEXT.md`

#### Scenario: A conflict at the final push
- **WHEN** the final push rebases onto a `main` that conflicts with the branch after a checkpoint kept the passed groups
- **THEN** the item stops with the class `conflict`, the comment names the conflicting path, and `origin` keeps the item branch

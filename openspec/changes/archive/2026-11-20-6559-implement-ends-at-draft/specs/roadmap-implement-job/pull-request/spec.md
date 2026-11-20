## ADDED Requirements

### Requirement: The run ends at the draft pull request
After the job sets the title and the body of the draft pull request and comments the outcome of each step, it SHALL end the run of the item: it SHALL record `implement.result` as `drafted`, the number of the pull request, the last commit and the spend, set Status to In Review, and comment the spend on the item. The job SHALL NOT watch the checks of the pull request, publish an evidence comment, run `gh pr ready` or merge.

#### Scenario: The end of a run
- **WHEN** every group passes and the job pushes the branch
- **THEN** the draft holds the final title and body, `gh pr ready` ran never, the record holds `implement.result` equal to `drafted` and the number of the pull request, and Status is In Review

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

## MODIFIED Requirements

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

### Requirement: The job skips a phase that passed at the same head
The job SHALL write `implement.checked_sha` with the head after the scoped checks pass, and `implement.published_sha` with the head after it pushes the item branch. A job whose head equals `implement.checked_sha` SHALL run no scoped check. A job whose head equals `implement.published_sha` SHALL push nothing. The job SHALL clear both keys when the run ends at the draft and when it returns the item to New.

#### Scenario: A second Job at a checked head
- **WHEN** a first Job passes the scoped checks, pushes, and stops before the end of the run, and a second Job starts at the same head
- **THEN** the second Job runs no scoped check and pushes nothing, and the record holds both keys until the run ends at the draft

#### Scenario: A head that moved
- **WHEN** `implement.checked_sha` holds a sha that is not the head
- **THEN** the job runs the scoped checks and writes the new head

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

### Requirement: The run ends at the draft pull request
After the job sets the title and the body of the draft and comments each step, it SHALL ask `draft_readiness` with no check runs, and a refusal SHALL stop the item at the step `ready`. Then it SHALL end the run: it SHALL record `implement.result` as `drafted`, the pull request, the last commit and the spend, set Status to In Review, and comment the spend on the item. The job SHALL NOT watch the checks, publish an evidence comment, run `gh pr ready` or merge.

#### Scenario: The end of a run
- **WHEN** every group passes and the job pushes the branch
- **THEN** the draft holds the final title and body, `gh pr ready` ran never, the record holds `implement.result` equal to `drafted` and the number of the pull request, and Status is In Review

#### Scenario: A draft that the readiness function refuses
- **WHEN** the archive leaves a task of group 2 unticked
- **THEN** the item is Blocked at the step `ready` with the class `plan_defect`, and the record holds no `implement.result` equal to `drafted`

### Requirement: A Planned item gets a new branch
For a Planned item the job SHALL make the branch `<type>/<issue>-<slug>` at `origin/<default branch>`. The type is the Conventional Commit type of the title of the item, and the slug is the one of the change folder. The job SHALL run the groups that have an unticked task, regenerate the documentation and archive the change, as it does for a Staged item.

#### Scenario: Two groups
- **WHEN** a Planned item has a change with two unticked groups on `origin/main`, both steps pass, and the checks pass
- **THEN** `origin` holds the new branch with one commit for each group, one for the documentation and one for the archive, GitHub received one draft pull request and one body that starts with `Closes #<issue>`, `gh pr ready` ran never, `implement.result` is `drafted`, the record holds `implement.branch` and `implement.pr`, and the Status is In Review

#### Scenario: A group that is done
- **WHEN** every task of group 1 is ticked on `origin/main`
- **THEN** the job runs a step for group 2 only

## REMOVED Requirements

### Requirement: A pull request that passes its checks is marked ready
**Reason**: The implement Job ends at the draft pull request and watches no check (#6559).
**Migration**: The watch row runs the ready path of the step `fix-checks` on the draft, and the watch row starts a fix-checks Job for a failed check of the classes `test`, `lint`, `types` and `plan_defect` (specs `roadmap-watch-row` and `roadmap-fix-checks`).

### Requirement: The watch reads check runs and no commit status
**Reason**: The implement Job ends at the draft pull request and watches no check (#6559).
**Migration**: The watch row reads the check runs of a bot pull request.

### Requirement: The job pushes the work in progress of a step
**Reason**: The implement Job makes no work-in-progress commit and no work-in-progress push (#6559).
**Migration**: A checkpoint pushes each group that passed, and a step that stops resets the checkout to the commit where it started.

### Requirement: The job records the work in progress of a step
**Reason**: The implement Job makes no work-in-progress commit and no work-in-progress push (#6559).
**Migration**: No record replaces `implement.wip`.

### Requirement: A second Job resumes from the kept work
**Reason**: The implement Job makes no work-in-progress commit and no work-in-progress push (#6559).
**Migration**: A checkpoint pushes each group that passed, and a step that stops resets the checkout to the commit where it started.

### Requirement: The stop comment names the kept work
**Reason**: The implement Job makes no work-in-progress commit and no work-in-progress push (#6559).
**Migration**: The stop comment of a stop in the scoped checks names the branch and its last commit.

### Requirement: The watch stops the item on a merged or closed pull request
**Reason**: The implement Job ends at the draft pull request and watches no check (#6559).
**Migration**: The status sync of the watch row reads a merged or closed pull request.

### Requirement: A push rebases onto the default branch
**Reason**: The implement Job makes no work-in-progress commit and no work-in-progress push (#6559).
**Migration**: The requirement "A push rebases the checkout onto the default branch" holds the rule.

### Requirement: A conflicting push keeps the head on the item branch
**Reason**: The implement Job makes no work-in-progress commit and no work-in-progress push (#6559).
**Migration**: The requirement "A conflicting checkpoint or stop push keeps the head on the item branch" holds the rule.

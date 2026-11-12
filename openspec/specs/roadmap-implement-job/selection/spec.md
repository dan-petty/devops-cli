# roadmap-implement-job/selection Specification

## Purpose
The items that an implement round takes: the filter, the order, the effort passes, the items that it leaves out, and the plan check that it runs once for each run.

## Requirements

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

### Requirement: The implement round refuses an empty repository
`run_implement_round` SHALL raise `RoadmapImplementError` before any request to the cluster or to GitHub when `repo` is empty, because each counter of the round carries the label `repo`.

#### Scenario: A round with no repository
- **WHEN** a round runs with an empty `repo`
- **THEN** it raises `RoadmapImplementError` and sends no request to the cluster

### Requirement: The plan check reads a nested capability
The plan reader SHALL read a spec file at any depth under `openspec/specs/` of a commit, and a spec delta at any depth under `specs/` of a change folder, as the capability of its folder path, such as `roadmap-stage/paths-gate`.

#### Scenario: The base specs of a commit hold a nested capability
- **WHEN** a commit holds `openspec/specs/roadmap-stage/paths-gate/spec.md` with the requirement "A path exists"
- **THEN** the base specs of the commit hold the capability `roadmap-stage/paths-gate` with that requirement

#### Scenario: A plan with a delta of a nested capability
- **WHEN** a change folder holds `specs/roadmap-stage/paths-gate/spec.md`
- **THEN** the reader gives the spec delta of the capability `roadmap-stage/paths-gate`

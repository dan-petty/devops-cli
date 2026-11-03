## ADDED Requirements

### Requirement: A request of a stopped step is judged before the item stops
When a step stops and its last message holds a request (`roadmap-plan-amendment`), the job SHALL judge the request before it stops the item. It SHALL commit an applied amendment as `docs(openspec): amend the plan of group <n> (#N)`, read `tasks.md` again, and run the same group again. It SHALL apply one amendment for each group.

#### Scenario: A wrong test path in the plan
- **WHEN** group 1 names a test path that is no file, the first step changes no file and ends with a `path` request for the tracked file with the same name, and the second step does the group
- **THEN** the item reaches a ready pull request, `origin` holds the commit `docs(openspec): amend the plan of group 1 (#1)`, and the archived `tasks.md` holds the corrected path and one bullet in `## Amendments`

#### Scenario: A second request for the same group
- **WHEN** the second step of group 1 stops with another valid request
- **THEN** the job applies nothing, the item is Blocked, and the comment quotes the request as a question

#### Scenario: A stop with no request
- **WHEN** a step stops and its last message holds no `plan-request` block
- **THEN** the job stops the item as it does for any stop

### Requirement: A stop after an amendment names the action taken
When the job applied an amendment for the group that stops the item with the class `plan_defect`, the stop comment SHALL name `amend` as the action taken and `wait` as the action left.

#### Scenario: The amended group fails again
- **WHEN** the job applied a `path` amendment to group 1, and the step of group 1 stops with "The agent changed no file."
- **THEN** the comment holds the class `plan_defect`, the action taken `amend` and the action left `wait`

### Requirement: The comment on the pull request lists each amendment with its evidence
The comment of the job on the pull request SHALL show one line for each applied amendment and each split: the group, the kind, the defect, the evidence, and the old and the new text. A stopped item whose pull request exists SHALL get the same lines in a comment.

#### Scenario: An amended run
- **WHEN** the job applied a `path` amendment and reaches the ready pull request
- **THEN** the comment on the pull request holds a line with the group, `path`, the defect, the evidence, `old` and `new`

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

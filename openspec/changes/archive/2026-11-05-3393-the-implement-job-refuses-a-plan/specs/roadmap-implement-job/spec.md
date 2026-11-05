## ADDED Requirements

### Requirement: The job leaves out an item whose plan fails the check
The implement selection SHALL run `check_proposal` on the plan of a Staged or Planned item before it returns a target, and it SHALL leave the item out with the first problem as its reason when the check returns problems.

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

## MODIFIED Requirements

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

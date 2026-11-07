## MODIFIED Requirements

### Requirement: An unmapped criterion is refused
`check_proposal` SHALL refuse a reply that leaves an acceptance criterion of the issue with no entry in `criteria`, an entry that names a group the plan does not have, and an entry whose text is not an acceptance criterion that a person wrote in the issue body. The problem SHALL quote the exact text of the entry. The check SHALL read the body of the issue with the block of the refine job cut off, so a list inside that block is no criterion. The stage prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` SHALL state that the check refuses an entry that no person wrote.

#### Scenario: One of three criteria is unmapped
- **WHEN** The issue has three acceptance criteria and the reply's `criteria` list maps only two
- **THEN** `check_proposal` returns a problem that quotes the text of the unmapped criterion

#### Scenario: The retry copies the text
- **WHEN** The first reply leaves a criterion out and the second reply maps it
- **THEN** the second request to the model holds the problem with the exact text, and the item is staged

#### Scenario: An entry names a group that does not exist
- **WHEN** An entry of `criteria` names group 3 and the plan has 2 groups
- **THEN** `check_proposal` returns a problem that names the criterion and the count of groups

#### Scenario: An entry copies a criterion of the refine block
- **WHEN** The issue body has no `Acceptance criteria` heading outside the refine block and the reply holds one criterion of the refine block
- **THEN** `check_proposal` returns one problem that quotes the copied criterion and says that no person wrote it

#### Scenario: An issue with no person-written list takes an empty list
- **WHEN** The issue body has no `Acceptance criteria` heading outside the refine block and the reply's `criteria` list is empty
- **THEN** `check_proposal` returns no problem for the criteria mapping

### Requirement: The replay judges the criteria gate on plans with a criteria list
The golden-set replay SHALL run the `criteria` gate on a plan that has a `criteria` list, and SHALL not judge a recorded plan that has none. The `paths` gate SHALL give `check_proposal` the issue body of a plan that has a `criteria` list, so the criteria rule reads the same body as the stage job, and SHALL give no body for a plan that has none.

#### Scenario: A plan leaves a criterion out
- **WHEN** The replay runs a plan with a `criteria` list that leaves one criterion of its issue out
- **THEN** the `criteria` gate refuses the plan

#### Scenario: A recorded plan has no list
- **WHEN** The replay runs a recorded plan with no `criteria` key
- **THEN** the `criteria` gate finds no problem

#### Scenario: The paths gate reads the body of a plan with a criteria list
- **WHEN** The replay runs a plan whose `criteria` entry copies a criterion that a person wrote in its issue
- **THEN** the `paths` gate returns no problem for that entry

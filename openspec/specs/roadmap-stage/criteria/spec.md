# roadmap-stage/criteria Specification

## Purpose
The acceptance criteria of a plan: the map from each criterion of the issue to a task group, the refusal of an unmapped criterion, and the criteria section of tasks.md.

## Requirements

### Requirement: Criteria mapping in the stage reply
The stage reply SHALL hold a `criteria` list in which each entry gives the text of one acceptance criterion of the issue and either the number of the group that delivers it or `pending-person` with a reason. An acceptance criterion SHALL be a top-level item of a list under a heading `Acceptance criteria` in the text of the issue body that a person wrote, before the block of the refine job. An issue with no such list SHALL have no criterion.

#### Scenario: Every criterion is mapped
- **WHEN** The issue has three acceptance criteria and the reply's `criteria` list holds an entry for each, with a group number or `pending-person` and a reason
- **THEN** `check_proposal` returns no problem for the criteria mapping

#### Scenario: The list of the refine block is not read
- **WHEN** The issue body holds a list under `Acceptance criteria` in the refine block as well, and the reply maps the items of the list that a person wrote
- **THEN** `check_proposal` returns no problem for the criteria mapping

#### Scenario: The issue has no acceptance list
- **WHEN** The issue body has no heading `Acceptance criteria` and the reply's `criteria` list is empty
- **THEN** `check_proposal` returns no problem for the criteria mapping

#### Scenario: A pending-person entry has no reason
- **WHEN** An entry of `criteria` gives `pending-person` and a blank reason
- **THEN** the reply breaks the schema and goes back to the model
### Requirement: A pending-person criterion resolves through the issue's own text
`criterion_problems` SHALL resolve a `pending-person` entry whose criterion the reader cut at a comma to the longest acceptance criterion of the issue that the entry's criterion and reason start with, and the rest of the text SHALL be the reason.

#### Scenario: A pending-person criterion with a comma
- **WHEN** the entry's criterion is `Add the label` and its reason is `keep the title, because the label is missing`, and the issue criterion is `Add the label, keep the title`
- **THEN** the entry maps to `Add the label, keep the title` with no problem

#### Scenario: A pending-person reason with a comma
- **WHEN** the entry's criterion is `Add the label` and its reason is `because the label is missing, and the title is short`, and the issue criterion is `Add the label`
- **THEN** the entry keeps the whole reason and maps with no problem

#### Scenario: The longest criterion wins
- **WHEN** the issue holds `Add the label` and `Add the label, keep the title`, and the entry reads `Add the label` with the reason `keep the title, because the label is missing`
- **THEN** the entry maps to `Add the label, keep the title`

#### Scenario: No criterion matches
- **WHEN** the entry reads `Unknown text` and the issue holds no such criterion
- **THEN** `criterion_problems` reports the unmatched entry

### Requirement: An unmapped criterion is refused
`check_proposal` SHALL refuse a reply that leaves an acceptance criterion of the issue with no entry in `criteria`, and an entry that names a group the plan does not have. The problem SHALL quote the exact text of the criterion. The check SHALL read the whole body of the issue.

#### Scenario: One of three criteria is unmapped
- **WHEN** The issue has three acceptance criteria and the reply's `criteria` list maps only two
- **THEN** `check_proposal` returns a problem that quotes the text of the unmapped criterion

#### Scenario: The retry copies the text
- **WHEN** The first reply leaves a criterion out and the second reply maps it
- **THEN** the second request to the model holds the problem with the exact text, and the item is staged

#### Scenario: An entry names a group that does not exist
- **WHEN** An entry of `criteria` names group 3 and the plan has 2 groups
- **THEN** `check_proposal` returns a problem that names the criterion and the count of groups

### Requirement: Criteria section in tasks.md
The `tasks.md` of a staged plan SHALL hold a `## Criteria` section before `## Workflow follow-up`. It SHALL list each criterion as a bullet with no checkbox, and each bullet SHALL start with a fixed word: `Group <n>:` and the criterion, or `Pending person:`, the criterion and the reason. A criterion that reads as a heading or a task SHALL add no group and no task.

#### Scenario: Staged plan shows the mapping
- **WHEN** A plan is rendered with criteria mapped to groups
- **THEN** `tasks.md` holds a `## Criteria` section with one line for each criterion, as `Group <n>: <criterion>` or `Pending person: <criterion>, <reason>`

#### Scenario: A plan with no criterion has no section
- **WHEN** A plan is rendered with an empty `criteria` list
- **THEN** `tasks.md` holds no `## Criteria` section

#### Scenario: A criterion that reads as a heading
- **WHEN** a criterion of the issue is `## 2. Cleanup`
- **THEN** the gate accepts the entry that copies it, and `tasks.md` holds the group 1 only

### Requirement: A split moves the criteria with the groups
The split request SHALL hold the `criteria` list, the split reply SHALL give it again with the numbers of the new groups, and the job SHALL check it as it checks the first reply.

#### Scenario: A split renumbers the groups
- **WHEN** The model splits a group and gives the criteria with the new group numbers
- **THEN** `tasks.md` shows the new numbers

### Requirement: The replay judges the criteria gate on plans with a criteria list
The golden-set replay SHALL run the `criteria` gate on a plan that has a `criteria` list, and SHALL not judge a recorded plan that has none.

#### Scenario: A plan leaves a criterion out
- **WHEN** The replay runs a plan with a `criteria` list that leaves one criterion of its issue out
- **THEN** the `criteria` gate refuses the plan

#### Scenario: A recorded plan has no list
- **WHEN** The replay runs a recorded plan with no `criteria` key
- **THEN** the `criteria` gate finds no problem

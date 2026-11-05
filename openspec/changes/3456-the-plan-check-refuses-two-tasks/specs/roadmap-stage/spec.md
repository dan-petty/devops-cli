## ADDED Requirements

### Requirement: Two tasks of a plan state different work
`check_proposal` SHALL refuse two tasks whose normalized work text is the same, and SHALL name both task numbers and the group or groups of those tasks.

#### Scenario: Duplicate task in one group
- **WHEN** group 2 holds task 2.1 and task 2.3 with the same normalized work text
- **THEN** `check_proposal` returns a problem that names task 2.1, task 2.3 and group 2

#### Scenario: Duplicate task across two groups
- **WHEN** group 2 task 2.1 and group 4 task 4.2 hold the same normalized work text
- **THEN** `check_proposal` returns a problem that names task 2.1, task 4.2, group 2 and group 4

#### Scenario: Two tasks share a verification command
- **WHEN** group 3 task 3.1 and task 3.2 hold different work text and the same `Verification:` command
- **THEN** `check_proposal` returns no duplicate-task problem for task 3.1 and task 3.2

#### Scenario: A documentation task repeats an implementation task
- **WHEN** an `other` group 3 holds task 3.1 that adds a paragraph and task 3.2 that adds the same paragraph with the docs command
- **THEN** `check_proposal` returns a duplicate-task problem that names task 3.1 and task 3.2

#### Scenario: Work text that differs only in spacing and case
- **WHEN** group 1 task 1.1 and task 1.2 hold the same words with different runs of spaces and different case
- **THEN** `check_proposal` returns a duplicate-task problem for task 1.1 and task 1.2

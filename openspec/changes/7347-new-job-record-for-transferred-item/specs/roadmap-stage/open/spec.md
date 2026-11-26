## ADDED Requirements

### Requirement: The open row takes a recorded branch that names the item
The open row SHALL take the branch of `implement.branch` of an open item as a candidate only when the branch has the form `<type>/<issue>-<slug>` with the number of the item.

#### Scenario: One recorded branch names its item and one names no issue
- **WHEN** item 1 records the pushed branch `test/1-one` and item 2 records the pushed branch `docs/release-notes`, and no pull request is open
- **THEN** the candidates of the row hold the branch of item 1 only

### Requirement: The open step records the head branch of a plan
The open step SHALL record the head branch of a plan pull request as `stage.branch`, in the write that records `stage.pr`, when the branch has the form `<type>/<issue>-<slug>` with the number of the item. For any other head branch the step SHALL record `stage.pr` only.

#### Scenario: The head branch names the item
- **WHEN** the step opens the plan pull request 501 of item 1 from the branch `docs/1-plan-the-open-step`
- **THEN** one write records `stage.pr` `501` and `stage.branch` `docs/1-plan-the-open-step`

#### Scenario: The head branch names no item
- **WHEN** the step opens the plan pull request 501 of item 1 from the branch `plan-branch`
- **THEN** the step records `stage.pr` `501` and no `stage.branch`

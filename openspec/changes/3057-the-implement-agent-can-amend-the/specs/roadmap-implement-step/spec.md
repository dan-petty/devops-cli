## ADDED Requirements

### Requirement: A step applies a bounded plan amendment
The implement step SHALL apply a bounded plan amendment in the same pull request when it finds a wrong path, a missing task, a group over its token budget or a wrong verify command.

#### Scenario: Wrong test path in the plan
- **WHEN** A step finds a test path in its group that does not exist in the checkout
- **THEN** The step corrects the path in `tasks.md` and continues

### Requirement: The amendment is recorded in tasks.md
The implement step SHALL record each applied amendment in the change folder's `tasks.md` with the defect, the evidence and the corrected text.

#### Scenario: Amendment entry in tasks.md
- **WHEN** The step applies a bounded amendment
- **THEN** The `tasks.md` of the change folder holds an amendment entry with the defect, the evidence and the corrected text

### Requirement: The amendment is posted on the pull request
The implement step SHALL post each applied amendment and its evidence as a comment on the pull request that delivers the item.

#### Scenario: Pull request comment with the amendment
- **WHEN** The step applies a bounded amendment
- **THEN** The pull request has a comment with the amendment text and its evidence

### Requirement: A false premise returns the item
The implement step SHALL return the item to New with the evidence and no committed code when it finds a false premise.

#### Scenario: False premise in the plan
- **WHEN** A step finds that a premise of the plan is false against the checkout
- **THEN** The item is returned to New with the evidence and the step commits no code

### Requirement: A scope change waits for a person
A plan amendment SHALL NOT change a spec requirement or an acceptance criterion without a person's approval.

#### Scenario: Scope change blocked
- **WHEN** A step finds a defect whose fix changes a spec requirement or an acceptance criterion
- **THEN** The step posts a question on the issue and applies no change

### Requirement: An over-budget group is re-split
The implement step SHALL re-split a group whose inputs exceed the token budget through the split step of the stage job and continue with the new groups.

#### Scenario: Group over its budget
- **WHEN** The inputs of a group exceed the token budget of the step
- **THEN** The split step re-splits the group and the job runs the new groups

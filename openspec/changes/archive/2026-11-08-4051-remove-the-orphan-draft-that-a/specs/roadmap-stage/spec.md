## ADDED Requirements

### Requirement: A staged item records its intent before the push
The job SHALL write the mark `stage.pending`, the branch name and the time as JSON, with one write of marks before it pushes the branch of an item. The write of the marks after the draft SHALL clear `stage.pending` with the other keys.

#### Scenario: The request cost of a staged item
- **WHEN** a round stages one item
- **THEN** the round writes the marks twice for that item, and the record holds no `stage.pending` at the end

### Requirement: An old intent mark with no recorded pull request gives an orphan
In each run the job SHALL look at the open items that hold `stage.pending` and no `stage.pr`, and SHALL use the branch name of the mark. A mark younger than 1 hour SHALL give no action. A branch that is not on `origin` SHALL give only the clear of the record.

#### Scenario: The marks write fails
- **WHEN** the write of the marks after the draft fails, and a later round runs after the mark is 1 hour old
- **THEN** the round closes the draft, deletes the branch and clears the record, and a following round plans the item again

#### Scenario: The worker dies after the push
- **WHEN** the worker dies after the push and before the draft, and a later round runs after the mark is 1 hour old
- **THEN** the round deletes the branch, makes no request to close a draft and clears the record

#### Scenario: A retitle changes the slug
- **WHEN** a person changes the title of the item between the failure and the next round
- **THEN** the round still finds the orphan by the branch name of the mark

#### Scenario: A young mark
- **WHEN** the mark is younger than 1 hour
- **THEN** the job makes no request and keeps the mark, and a round that runs when the mark is 1 hour old judges it

#### Scenario: The branch is gone
- **WHEN** the branch of the mark is not on `origin`
- **THEN** the job clears the record and makes no request

### Requirement: The job removes an orphan only when it wrote the branch alone
When every commit of the pushed branch of an orphan past the default branch is by the identity of the clone or is a clean merge, the job SHALL close the open pull request whose head is the branch, delete the branch and clear the record. The job SHALL read the open pull requests once in a round, and only when such a branch exists. When any other commit exists, the job SHALL keep the branch and the draft and say so in the plan.

#### Scenario: A person added a commit
- **WHEN** the pushed branch of the mark holds a commit by another author
- **THEN** the job keeps the branch and the draft, makes no request and the plan says why

#### Scenario: The request cost of a removal
- **WHEN** a round removes two orphans
- **THEN** the round reads the open pull requests once

### Requirement: A branch with no intent mark is never touched
The job SHALL NOT close, delete or change a pushed branch or a pull request whose item holds no `stage.pending`.

#### Scenario: A branch with no mark
- **WHEN** a person or an agent pushed a branch for another item that holds no `stage.pending`
- **THEN** the job does not touch the branch or its pull request

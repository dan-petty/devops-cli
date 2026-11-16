# roadmap-pr-review Specification

## Purpose
The step `devops roadmap step review` gives each open bot pull request one verdict of the review gate (mergeable, needs fix, discard plan, discard implementation, issue changed), records it as a verdict label that the grades read, and takes the next action of the verdict, so a bot pull request does not wait for a person to find out what it needs.

## Requirements

### Requirement: The facts decide the verdict before a model
The step SHALL read the facts first: the check runs of the head, the merge state, the labels, the item and its record, the files of the diff, the merged related pull requests since the merge base, the review threads and the open findings of a plan. A closed item, a changed issue text or merged work on the change folder SHALL give issue changed. A conflict, a failed check, an open finding, a thread or an incomplete change SHALL give needs fix.

#### Scenario: An issue text edit after the plan is issue changed
- **WHEN** the hash of the issue text is not the recorded `stage.text_hash`
- **THEN** the verdict is issue changed and the model gets no request

#### Scenario: A failed check leaves fix-checks
- **WHEN** a check that is not of CI infrastructure failed on the head of a delivery
- **THEN** the verdict is needs fix with the due fix `fix-checks`, the evidence names the check, and the model gets no request

#### Scenario: A plan that needs a fix leaves fix-plan
- **WHEN** a plan has a conflict, a failed check, an open finding or the label `verdict/fix-plan`
- **THEN** the verdict is needs fix with the due fix `fix-plan`

#### Scenario: Checks that run give no verdict
- **WHEN** a check still runs, the head reports no check run, or only CI infrastructure failed
- **THEN** the step returns `wait` and writes nothing

### Requirement: The model decides only what the facts leave open
When no rule applies, the step SHALL ask the model of the task `ai.tasks.review`, whose code default is DeepSeek, whether the diff does what the plan and the issue ask. The step SHALL keep only evidence that names a file of the diff, and a discard with no such evidence SHALL become needs fix. A request over `roadmap.review.token_budget` SHALL send nothing and fail with the class `limit_reached`.

#### Scenario: A discard with no evidence becomes needs fix
- **WHEN** the model answers discard and names no file of the diff
- **THEN** the verdict is needs fix

#### Scenario: A request over the cap sends nothing
- **WHEN** the request of the review is over `roadmap.review.token_budget`
- **THEN** the judge raises an error that names the setting and sends no model request

### Requirement: The step writes one verdict and its next action
With `--confirm` in the mode `on`, the step SHALL read the head again, post one comment with the verdict, the reason and the evidence, and set the verdict label of the kind of the pull request. Mergeable SHALL mark a draft ready with the judged head; needs fix and issue changed SHALL make a ready one a draft. A discard SHALL close the pull request, delete its branch with a lease on the head, and return the item to New with the keys of its plan or delivery cleared.

#### Scenario: Mergeable marks the draft ready
- **WHEN** the verdict of a draft delivery is mergeable
- **THEN** the step labels it `verdict/mergeable`, removes its other own verdict labels, comments, marks it ready, and counts one verdict

#### Scenario: A ready pull request that needs a fix becomes a draft
- **WHEN** the verdict of a pull request that is ready for review is needs fix or issue changed
- **THEN** the step makes it a draft again with the judged head

#### Scenario: A discarded delivery returns its item
- **WHEN** the verdict of a delivery is discard implementation
- **THEN** the step closes the pull request, deletes its branch with a lease on the judged head, and the item is New with no `implement.pr`

#### Scenario: A moved head writes nothing
- **WHEN** the head moves between the read and the first write
- **THEN** the step returns `skipped` and writes no comment, no label and no mark

### Requirement: The step guards and caps its reviews
The step SHALL send no request in the mode `off`, and SHALL write nothing without `--confirm` or in the mode `plan`. It SHALL skip a pull request that is not open, whose head moved from `--head`, whose item a live runner Job holds, or whose head and issue text have a verdict. It SHALL stop on a pull request of a person or an owner label. At `roadmap.review.rounds` verdicts it SHALL leave the pull request for a person with one comment.

#### Scenario: The mode off sends no request
- **WHEN** `roadmap.review.mode` is `off`
- **THEN** the step returns `skipped` and sends no request

#### Scenario: Without confirm the step plans
- **WHEN** the step runs without `--confirm`
- **THEN** it returns the verdict and the action that it would take, and writes nothing

#### Scenario: A live runner Job skips the review
- **WHEN** the record of the item names an implement Job with no recorded state
- **THEN** the step returns `skipped` with no model request and no comment

#### Scenario: The cap of verdicts leaves the pull request for a person
- **WHEN** the pull request has 3 verdicts
- **THEN** the step posts one comment for a person, returns `capped`, and asks no model

### Requirement: The grades read the verdict that the step writes
Each label that the step writes SHALL read back as its verdict in `devops roadmap eval grades`. Each judged or failed attempt SHALL log one result line of the job `review`.

#### Scenario: A label of the step scores in the grades
- **WHEN** the step labels a delivery `verdict/fix-implementation`
- **THEN** the grades read the label event as needs fix and score it with the partial score

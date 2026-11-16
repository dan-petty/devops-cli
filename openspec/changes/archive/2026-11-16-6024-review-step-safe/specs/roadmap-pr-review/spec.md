## MODIFIED Requirements

### Requirement: The step writes one verdict and its next action
With `--confirm` in the mode `on`, the step SHALL read the head again, post one comment with the verdict, the reason and the evidence, and set the verdict label of the kind of the pull request. Mergeable SHALL mark a draft ready with the judged head; needs fix and issue changed SHALL make a draft again of a pull request that a bot marked ready. A discard of the model alone SHALL only label and comment, and a person decides the close.

#### Scenario: Mergeable marks the draft ready
- **WHEN** the verdict of a draft delivery is mergeable
- **THEN** the step labels it `verdict/mergeable`, removes its other own verdict labels, comments, marks it ready, and counts one verdict

#### Scenario: A ready pull request that needs a fix becomes a draft
- **WHEN** the verdict of a pull request that a bot marked ready for review is needs fix or issue changed
- **THEN** the step makes it a draft again with the judged head

#### Scenario: A discarded delivery returns its item
- **WHEN** the verdict of a delivery is a discard implementation of a rule
- **THEN** the step deletes its branch with a lease on the judged head, then closes the pull request, and the item is New with no `implement.pr`

#### Scenario: A moved head writes nothing
- **WHEN** the head moves between the read and the first write
- **THEN** the step returns `skipped` and writes no comment, no label and no mark

#### Scenario: A discard of the model alone closes nothing
- **WHEN** the model alone gives a discard
- **THEN** the step labels the pull request and comments that a person decides, and closes nothing, deletes no branch and needs no withdraw

#### Scenario: The ready mark of a person stays
- **WHEN** a person marked the pull request ready and the verdict is needs fix
- **THEN** the pull request stays ready, and the action says that a person marked it ready

### Requirement: The step guards and caps its reviews
The step SHALL send no request in the mode `off`, and SHALL write nothing without `--confirm` or in the mode `plan`. It SHALL skip a pull request whose head moved from `--head`, or whose item a live runner Job or stage Job holds. It SHALL stop on a pull request of a person or a claim label other than `owner/service`. It SHALL run the rules on each call and ask the model once for each head and issue text. At `roadmap.review.rounds` verdicts it SHALL leave the pull request for a person.

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

#### Scenario: A live stage Job skips the review
- **WHEN** the record of the item names a stage Job (`stage.job`)
- **THEN** the step returns `skipped` with no model request and no comment

#### Scenario: The claim of the Service does not stop the review
- **WHEN** the item and the pull request hold `owner/service`
- **THEN** the step judges the pull request

#### Scenario: A new fact on a judged head gives a new verdict
- **WHEN** a plan that has the verdict mergeable on its head gets the label `verdict/fix-plan`
- **THEN** the step gives needs fix with `fix-plan` and asks no model again

## ADDED Requirements

### Requirement: A discard of a rule ends in an order that a later call repairs
A discard of a rule SHALL check the shared branch and the withdraw before the first write, then record its start, delete the branch with a lease on the judged head, close the pull request, and return the item. A call on the closed pull request with that record SHALL end the discard. A branch that holds the work of the plan and of its delivery SHALL be left for a person.

#### Scenario: A failed delete closes nothing
- **WHEN** the delete of the branch fails
- **THEN** the pull request stays open and the item keeps its keys, so the next call tries again

#### Scenario: A call on the closed pull request ends the discard
- **WHEN** the pull request closed after the delete and the item still records it with the start of the discard
- **THEN** the step deletes the branch if it is there and returns the item to New

#### Scenario: No withdraw writes nothing
- **WHEN** a discard of a rule has no withdraw
- **THEN** the step raises before it comments or labels

#### Scenario: A shared branch is left for a person
- **WHEN** `implement.branch` of a plan, or `stage.pr` of a delivery, names the branch of the pull request
- **THEN** the step comments that a person decides, and deletes and closes nothing

### Requirement: The watch row holds the ready mark of work that a verdict sent back
The watch row SHALL NOT mark ready a green bot pull request that holds a verdict label other than `verdict/mergeable`.

#### Scenario: A plan with Issue changed stays a draft
- **WHEN** a green plan draft of the bot holds `verdict/issue-changed`
- **THEN** the watch row does not mark it ready and records no `stage.ready`

#### Scenario: Mergeable does not hold the ready mark
- **WHEN** a green bot pull request holds only `verdict/mergeable`
- **THEN** the ready step is due

### Requirement: A wait on CI infrastructure has a limit
Each wait on a head whose only failed checks are of CI infrastructure SHALL log one line. With writes, the step SHALL record the time of the first wait of the head, and after `roadmap.review.infra_wait_hours` it SHALL comment once that a person runs the failed check again, and give no verdict.

#### Scenario: A long wait on CI infrastructure goes to a person
- **WHEN** the same head waited on CI infrastructure for `roadmap.review.infra_wait_hours`
- **THEN** the step returns `stopped` with one comment for a person

### Requirement: One Issue changed verdict answers one issue text
After an Issue changed verdict for an issue text, the same text SHALL give no second Issue changed verdict, so the updated work for that text gets its own verdict.

#### Scenario: The updated work of an edited issue is judged
- **WHEN** a new head comes for an issue text that an Issue changed verdict answered
- **THEN** the rules and the model judge the new head

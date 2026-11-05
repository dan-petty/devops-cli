## MODIFIED Requirements

### Requirement: A round leaves an item from an account without write access to a person
Without `--item`, `devops roadmap refine` SHALL take only an item whose `author_association` is OWNER, MEMBER or COLLABORATOR, or whose author login is equal to `service.github_app.bot_login` or to `github-actions[bot]`. Any other item, and an item with no association and no such login, SHALL wait on a person with a detail line that names its author, its association and `--item` with its number. It SHALL take no place under `--limit`, and the round SHALL make no model call for it. With `--item`, refine SHALL refine the open New or Ready item that it names, whoever opened it.

#### Scenario: A round with an item from an account with no association to the repository
- **WHEN** the backlog holds a New P2 item that an account with the association NONE opened and a New P3 item that the owner opened, and refine runs with `--limit 1`
- **THEN** refine asks the model about the owner's item only, and the report shows the other item waiting on a person with the detail "The author is unknown, and its association with the repository is NONE. A refine round refines only the items that the owner, a member or a collaborator opened, and the items that the Service App's bot or github-actions[bot] opened. A person refines this item with --item 1."

#### Scenario: A person names the item with --item
- **WHEN** refine runs with `--item` for that item, and the model gives a proposal that is ready
- **THEN** refine refines the item and sets it to Ready

#### Scenario: An item that a collaborator opened
- **WHEN** a member or a collaborator opened a New item
- **THEN** a round takes the item

#### Scenario: An item that a trusted bot opened
- **WHEN** the Service App's bot, or `github-actions[bot]`, opened a New item
- **THEN** a round takes the item

## ADDED Requirements

### Requirement: Refine reviews a Ready proposal for an item of a bot
When the proposal for an item whose author is the Service App's bot or `github-actions[bot]` is ready, refine SHALL send the issue and the proposal to the verification pass of the stage job, with the model of the task slot `ai.tasks.verification`, before it plans the deferred parts. With no open finding, refine SHALL set the item Ready and record `refine.judge` `approved`. Refine SHALL make no review call for an item of a person.

#### Scenario: The review approves
- **WHEN** the proposal for a New item of the Service App is ready, and the review finds no open defect
- **THEN** the item is Ready, its job record holds `refine.judge` `approved`, and the review made one call

#### Scenario: An item of the owner
- **WHEN** the proposal for a New item of the owner is ready
- **THEN** refine makes no review call, sets the item Ready and records no `refine.judge`

### Requirement: A refusal keeps the item New and lists each finding
A finding of a type that keeps a plan in draft, or a placeholder, with a quote that the input holds, SHALL be an open finding. With an open finding, refine SHALL keep the item New, record `refine.judge` `refused` and the next step `edit`, and write one comment that lists each open finding with its evidence. A finding that is not open SHALL be advice, and the comment SHALL NOT list it.

#### Scenario: The review refuses
- **WHEN** the review finds a `false_premise` that quotes the problem statement, and a `contrived_test` with no quote
- **THEN** the item stays New, its job record holds `refine.judge` `refused` and `refine.next_step` `edit`, and refine's one comment lists the `false_premise` with its evidence and does not list the `contrived_test`

#### Scenario: A quote that the input does not hold
- **WHEN** the review finds a `false_premise` whose quote is in no text of the input
- **THEN** the item is Ready and its job record holds `refine.judge` `approved`

### Requirement: The review looks again only after the body changes
Refine SHALL make no review call for an item that waits on its body edit, and for an item that holds `refine.judge` `approved` with an unchanged body. A body edit SHALL end the wait, and the next round SHALL review the new proposal.

#### Scenario: A second round on the same body
- **WHEN** a round follows the refusal and no one changed the body
- **THEN** the round leaves the item waiting on its body edit, makes no proposal call and no review call, and writes no second comment

#### Scenario: A body edit
- **WHEN** a person edits the body after the refusal, and the review finds no open defect
- **THEN** the next round makes one review call and sets the item Ready

#### Scenario: An approved item that a round looks at again
- **WHEN** a round looks again at an item that holds `refine.judge` `approved`, and its body is unchanged
- **THEN** refine keeps the approval and makes no review call

### Requirement: Refine tells the author of an item that the jobs do not trust one time
A round that leaves out an item that the jobs do not trust, and finds no comment that holds `CONST_ROADMAP_REFINE_OUTSIDE_MARKER` on it, SHALL write one comment that names the author, the association and `devops roadmap refine --item <number>`. A round that finds the marker SHALL write no comment. The comment SHALL not count as a reply to the model.

#### Scenario: Another bot opens an item
- **WHEN** `dependabot[bot]` opened a New item and two rounds run
- **THEN** the first round writes one comment that holds the marker and "Its author is dependabot[bot], and its association with the repository is CONTRIBUTOR.", the second round writes none, and neither round calls a model for the item

#### Scenario: An outside account opens an item
- **WHEN** an account with the association NONE opened a New item and two rounds run
- **THEN** the item has one comment that holds the marker after the second round

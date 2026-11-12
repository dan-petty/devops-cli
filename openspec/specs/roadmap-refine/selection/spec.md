# roadmap-refine/selection Specification

## Purpose
The items that a refine round takes without --item, the order in which it takes them, the cap on its comments, and the items that it leaves out or takes again.

## Requirements

### Requirement: Only the limit stops a refine round
Without `--item`, `devops roadmap refine` SHALL take up to `--limit` items in this order: each open milestone's New items, nearest milestone first, then the backlog's P0 and P1 New items, then the backlog's other New items, each place by priority. The number of Ready items in the open milestones and in the backlog SHALL NOT stop a round.

#### Scenario: A backlog full of Ready items
- **WHEN** the backlog holds twelve Ready items and New P3, P2, P1 and P3 items, an open milestone holds one New P3 item, and refine runs with `--limit 4`
- **THEN** refine asks the model about the milestone's item, the backlog's P1 item, the backlog's P2 item and the backlog's first P3 item, in that order, and about no other item

### Requirement: A round leaves an item from an account without write access to a person
Without `--item`, `devops roadmap refine` SHALL take only an item whose author the jobs trust (`roadmap-author-trust`). Any other item SHALL wait on a person with a detail line that names its author, its association and `--item` with its number. It SHALL take no place under `--limit`, and the round SHALL make no model call for it. With `--item`, refine SHALL refine the open New or Ready item that it names, whoever opened it, when its title type is listed.

#### Scenario: A round with an item from an account with no association to the repository
- **WHEN** the backlog holds a New P2 item that an account with the association NONE opened and a New P3 item that the owner opened, and refine runs with `--limit 1`
- **THEN** refine asks the model about the owner's item only, and the report shows the other item waiting on a person with the detail "The author is unknown, and its association with the repository is NONE. A refine round refines only the items that these accounts opened: the owner, a member, a collaborator, the Service App's bot and github-actions[bot]. A person refines this item with --item 1."

#### Scenario: A person names the item with --item
- **WHEN** refine runs with `--item` for that item, and the model gives a proposal that is ready
- **THEN** refine refines the item and sets it to Ready

#### Scenario: An item that a collaborator opened
- **WHEN** a member or a collaborator opened a New item
- **THEN** a round takes the item

#### Scenario: An item that a trusted bot opened
- **WHEN** the Service App's bot, or `github-actions[bot]`, opened a New item
- **THEN** a round takes the item

### Requirement: Refine writes at most two comments on one item in a day
Without `--item`, a refine round SHALL leave an item alone, with no model call and no comment, when refine wrote `CONST_ROADMAP_REFINE_MAX_COMMENTS_PER_ITEM` (2) comments that carry its marker on the item in the last 24 hours. The item SHALL wait on a person with the reason in the plan, and SHALL take no place under the round's limit. Comments older than 24 hours SHALL NOT count.

#### Scenario: Two refine comments within the day
- **WHEN** refine wrote two comments on an item 23 hours ago, another bot replied to each, and a round runs with `--confirm`
- **THEN** the round makes no model call and writes no comment, the item waits on a person with the reason, and one warning and one count name the cap

#### Scenario: Two refine comments older than the day
- **WHEN** the two comments and the replies are 25 hours old
- **THEN** the round refines the item and writes its comment

#### Scenario: Items at the cap fill no place
- **WHEN** another bot replied to two refine comments on each of three P0 items in the last hour, a P1 item is New, and a round runs with a limit of 3
- **THEN** the round refines the P1 item with one model call, and the three P0 items wait on a person

### Requirement: Each comment that the cap stops counts once
The cap stops the comment that would answer the item's newest comment. For each such comment that no earlier round recorded, `--confirm` SHALL record the comment's creation time in the item's job record as `refine.capped_after`, log one warning and add 1 to `devops_cli_roadmap_refine_comments_capped_total`. A round that finds the recorded comment still the newest SHALL write, log and count nothing for the item.

#### Scenario: A round with no newer comment counts nothing
- **WHEN** a round stopped the comment on an item at the cap, a second round runs, a person then replies, and a third round runs
- **THEN** the second round writes nothing, and the third round counts and logs one more stopped comment and records the reply's time

### Requirement: A person refines an item at the cap
`devops roadmap refine --item` SHALL refine the item it names at the cap on refine's comments, since a person asked for it, and SHALL count no stopped comment.

#### Scenario: A person refines an item at the cap
- **WHEN** a person runs `devops roadmap refine --item <number> --confirm` on an item at the cap
- **THEN** refine refines the item and posts its comment, and counts no stopped comment

### Requirement: An item the stage job returned gets one new look
Without `--item`, `devops roadmap refine` SHALL refine again an unchanged New item whose `refine.next_step` is `ready` when a comment of the stage job follows refine's last comment and the item holds no `stage.branch`, with no reply of a person and no body edit. An item that a person set back to New with no such comment SHALL keep waiting on a person, with the reason that a reply makes refine look again.

#### Scenario: A stage return follows refine's last comment
- **WHEN** refine set an item Ready, the stage job commented with its marker and set the item to New, and no person replied
- **THEN** the next round refines the item again, with one model call, and the item is not waiting

#### Scenario: A person sets the item back
- **WHEN** refine set an item Ready, a person set it to New with no comment, and the stage job wrote nothing after refine's last comment
- **THEN** the next round leaves the item waiting on a person with the reason that a reply makes refine look again, and makes no model call

### Requirement: A round bounds the new looks and the reads of a wait text
A round SHALL select no more items than its limit, new looks included. It SHALL read at most `CONST_ROADMAP_REFINE_MAX_WAIT_CHECKS` issues and at most as many files from the text of one wait. The dry-run plan of a round without `--item` SHALL list these reads with their bound.

#### Scenario: More returned items than the limit
- **WHEN** four items were returned by the stage job and the limit of the round is 2
- **THEN** the round refines two items and makes two model calls

#### Scenario: A text that names many issues and files
- **WHEN** a wait text names 12 open issues and 12 files
- **THEN** the round reads 5 issues and 5 files for the item

### Requirement: A round reviews a Ready item of a bot again when its approval ends
A round SHALL take a Ready item of a trusted bot when its approval does not hold. The approval does not hold when `refine.judge` is not `approved`, or when the body hashes differently from `refine.body_hash` and `refine.section_hash`. The round SHALL review the new proposal. With no open finding, the item SHALL stay Ready with a new approval. With an open finding, the item SHALL go back to New.

#### Scenario: A person edits the body of an approved item
- **WHEN** refine approved a Ready item of the Service App, and a person adds a line to the body outside the section of refine
- **THEN** the item has no approval that holds, the next round makes one proposal call and one review call, and the item stays Ready with a new approval

#### Scenario: The review refuses the edited body
- **WHEN** the review finds an open defect in the proposal for the edited body
- **THEN** the item goes back to New, its job record holds `refine.judge` `refused` and `refine.next_step` `retry`, and no job takes it

#### Scenario: An approval that holds
- **WHEN** a Ready item of the Service App holds `refine.judge` `approved` and its body is unchanged
- **THEN** a round does not take the item for this reason

### Requirement: Refine tells the author of an item that the jobs do not trust one time
A round that leaves out an item that the jobs do not trust, and finds no comment that holds `CONST_ROADMAP_REFINE_OUTSIDE_MARKER` on it, SHALL write one comment that names the author, the association and `devops roadmap refine --item <number>`. A round that finds the marker SHALL write no comment. The comment SHALL not count as a reply to the model.

#### Scenario: Another bot opens an item
- **WHEN** `dependabot[bot]` opened a New item and two rounds run
- **THEN** the first round writes one comment that holds the marker and "Its author is dependabot[bot], and its association with the repository is CONTRIBUTOR.", the second round writes none, and neither round calls a model for the item

#### Scenario: An outside account opens an item
- **WHEN** an account with the association NONE opened a New item and two rounds run
- **THEN** the item has one comment that holds the marker after the second round

### Requirement: The issue listing gives the count of comments
The roadmap store SHALL give each `Item` the count of comments on its issue as `comments`, as the issue listing carries it. A write to the body or the labels of the issue SHALL NOT change the count.

#### Scenario: Comments of a person
- **WHEN** a person writes two comments on an issue, and a job then writes a mark in its job record
- **THEN** the Item of the issue has `comments` 2

### Requirement: Refine leaves an item with an unlisted title type
`devops roadmap refine` SHALL NOT refine an item whose title type is not in `CONST_BRANCH_TYPES`, also with `--item`, and SHALL make no model call for it, so the item does not become Ready. The detail SHALL name the type and `invalid-title-type`. The item SHALL wait on a person when the type has no correction. The first round after a title with a listed type SHALL refine the item.

#### Scenario: A New item with a security title
- **WHEN** a round runs over a New item titled `security(ssh): verify node host keys`
- **THEN** the model records no request, the Status stays New, and the detail names `fix(security): verify node host keys` and `invalid-title-type`

#### Scenario: A type with no correction
- **WHEN** a round runs over a New item titled `wip(cli): finish the half-done work`
- **THEN** the item waits on a person, the detail names `wip`, and the model records no request

#### Scenario: The title gets a listed type
- **WHEN** the title of the security item becomes `fix(security): verify node host keys` and a round runs
- **THEN** refine refines the item and sets it Ready

#### Scenario: A person names the item with --item
- **WHEN** refine runs with `--item` for the item titled `wip(cli): finish the half-done work`
- **THEN** the model records no request, and the Status stays New

#### Scenario: The limit of a round
- **WHEN** a round with `--limit 1` runs over the `wip(cli)` item and a New item with a listed type
- **THEN** refine takes the item with the listed type

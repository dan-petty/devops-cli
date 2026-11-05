## ADDED Requirements

### Requirement: An item the stage job returned gets one new look
Without `--item`, `devops roadmap refine` SHALL refine again an unchanged New item whose `refine.next_step` is `ready` when a comment of the stage job follows refine's last comment and the item holds no `stage.branch`, with no reply of a person and no body edit. An item that a person set back to New with no such comment SHALL keep waiting on a person, with the reason that a reply makes refine look again.

#### Scenario: A stage return follows refine's last comment
- **WHEN** refine set an item Ready, the stage job commented with its marker and set the item to New, and no person replied
- **THEN** the next round refines the item again, with one model call, and the item is not waiting

#### Scenario: A person sets the item back
- **WHEN** refine set an item Ready, a person set it to New with no comment, and the stage job wrote nothing after refine's last comment
- **THEN** the next round leaves the item waiting on a person with the reason that a reply makes refine look again, and makes no model call

### Requirement: The model reads the evidence of a stage return
The request of a proposal call SHALL hold the key `stage_return`: the text of the newest comment of the stage job after refine's last comment on an item with no `stage.branch`, without the marker and cut to `CONST_ROADMAP_REFINE_MAX_REPLY_TOKENS`, or `null` when there is none. The comments of the stage job SHALL stay out of `replies`.

#### Scenario: The request after a return
- **WHEN** the stage job returned an item with the evidence "It returns a fixed text." and refine looks at the item again
- **THEN** `stage_return` holds "It returns a fixed text.", holds no marker, and `replies` is empty

#### Scenario: The request of an item with no return
- **WHEN** refine refines an item that the stage job never returned
- **THEN** `stage_return` is `null`

### Requirement: A second stage return on the same body waits on a person
A round that refines an unchanged item after a stage return SHALL record its body hash in `refine.returned_body_hash`. Any other round SHALL clear the key. An item whose `refine.returned_body_hash` equals its `refine.body_hash` and that the stage job returned again SHALL wait on a person, with the reason that the job returned it twice on the same body, and with no model call. A reply or a body edit SHALL end that wait.

#### Scenario: The second return
- **WHEN** refine set an item Ready, the stage job returned it, refine looked again and set it Ready, and the stage job returned it again
- **THEN** the item waits on a person with the reason "The stage job returned the item to New twice on the same body. A reply or a body edit makes refine look at it again." and the round makes no model call

#### Scenario: A body edit between two returns
- **WHEN** a person edits the body of an item after its first return
- **THEN** the next round refines the item and clears `refine.returned_body_hash`

### Requirement: A wait on a person ends when a cause that its text names ends
Without `--item`, `devops roadmap refine` SHALL look at an unchanged item that waits on a person again when an issue that the last refine comment on the item names closed at or after that comment, or a file that the comment names changed on the default branch at or after that comment. The named files SHALL NOT need to be in `refine.block_paths`. An issue that closed before the comment, an issue of another repository, and the number of the item itself SHALL end no wait.

#### Scenario: A named issue closes after the comment
- **WHEN** an item waits on a person, the last refine comment on it asks about #12, and #12 closes after the comment
- **THEN** the next round refines the item again

#### Scenario: A named issue closed before the comment
- **WHEN** the last refine comment names #12 and #12 closed before the comment
- **THEN** the item keeps waiting and the round makes no model call

#### Scenario: A named file changes with no recorded block path
- **WHEN** an item waits on a person with no `refine.block_paths`, its last refine comment names `src/sample.py`, and a commit on the default branch changes that file after the comment
- **THEN** the next round refines the item again

### Requirement: A round bounds the new looks and the reads of a wait text
A round SHALL select no more items than its limit, new looks included. It SHALL read at most `CONST_ROADMAP_REFINE_MAX_WAIT_CHECKS` issues and at most as many files from the text of one wait. The dry-run plan of a round without `--item` SHALL list these reads with their bound.

#### Scenario: More returned items than the limit
- **WHEN** four items were returned by the stage job and the limit of the round is 2
- **THEN** the round refines two items and makes two model calls

#### Scenario: A text that names many issues and files
- **WHEN** a wait text names 12 open issues and 12 files
- **THEN** the round reads 5 issues and 5 files for the item

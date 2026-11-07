## ADDED Requirements

### Requirement: The issue listing gives the count of comments
The roadmap store SHALL give each `Item` the count of comments on its issue as `comments`, as the issue listing carries it. A write to the body or the labels of the issue SHALL NOT change the count.

#### Scenario: Comments of a person
- **WHEN** a person writes two comments on an issue, and a job then writes a mark in its job record
- **THEN** the Item of the issue has `comments` 2

### Requirement: A read of the comments of a waiting item is recorded
When a round reads the comments of an item that waits and finds no reply, `--confirm` SHALL record `refine.comments_seen` (the count of the listing), `refine.commented_at` (the time of refine's last comment) and `refine.wait_refs` (the issues, then the paths, that the wait text names). A round that finds the same values in the record SHALL write nothing for the item.

#### Scenario: A wait on a person that names an issue and a path
- **WHEN** an item waits on a person, the text of refine's comment names issue 3 and the path `src/sample.py`, and a round runs with `--confirm`
- **THEN** the job record holds `refine.comments_seen` `1`, `refine.commented_at` with the time of refine's comment, and `refine.wait_refs` `#3,src/sample.py`

### Requirement: An unchanged waiting item costs no comment read
Without `--item`, a round SHALL read no comment of an item that waits on a blocker or on a person, whose body is unchanged and whose count of comments is the recorded `refine.comments_seen`. The item SHALL keep waiting on its next step, and the round SHALL make no model call for it.

#### Scenario: A second round after the record
- **WHEN** an item waits on an open blocker, and a round has recorded the read of its comments
- **THEN** the next round lists the item as waiting on its blocker, reads no comment of the item and makes no model call

### Requirement: The exits of a wait need no comment read
A round SHALL end the wait of an item whose count of comments is the recorded one, with no read of its comments, when every recorded blocker is closed, when a commit on the default branch changed a recorded `refine.block_paths` path at or after `refine.commented_at`, or, for a wait on a person, when an issue or a path of `refine.wait_refs` closed or changed after `refine.commented_at`. The `updated_at` of the item SHALL NOT be part of the check.

#### Scenario: A blocker closes
- **WHEN** a recorded wait holds a blocker, and a person closes the blocker
- **THEN** the next round refines the item, and the `updated_at` of the item is the one it had before

#### Scenario: A cited path changes
- **WHEN** a recorded wait cites `src/sample.py`, and a commit changes that path five minutes after `refine.commented_at`
- **THEN** the next round refines the item, and the `updated_at` of the item is the one it had before

### Requirement: A new comment ends the saving
A round SHALL read the comments of an item that waits when its count of comments differs from the recorded one. A reply since refine's last comment SHALL end the wait. A comment that is no reply SHALL cost one read, and the round SHALL record the new count.

#### Scenario: A reply
- **WHEN** a person replies to the comment of an item that waits on a person with a recorded wait
- **THEN** the next round reads the comments of the item and refines it

#### Scenario: A comment of another job
- **WHEN** the alternatives job comments on an item with a recorded wait
- **THEN** the next round reads the comments of the item once and keeps it waiting, and the round after it reads none

### Requirement: The dry run lists the record of a waiting item
The dry-run plan of a round without `--item` SHALL list the read of the issue and the write of its job record under the condition that the round read the comments of the waiting item and its job record does not hold what they gave. The plan with `--item` SHALL list none.

#### Scenario: The plan of a round
- **WHEN** `devops roadmap refine --dry-run` plans a round without `--item`, and a round with `--item 7`
- **THEN** only the first plan lists the record of the waiting item

# roadmap-refine/waits Specification

## Purpose
How a refined item waits: the paths and the blockers that cause a block, the end of a wait, and the reads of the comments of a waiting item.

## Requirements

### Requirement: Refine records the paths that cause a block
When refine leaves an item New with an open dependency or a suspected block, it SHALL record in the job record, as `refine.block_paths`, the paths of the proposal's `block_paths` that the checkout holds at the refined commit: each path one time, without its line, at most five, and none outside the repository. It SHALL record no path for a proposal with no open dependency and no suspected block.

#### Scenario: A proposal cites paths that the checkout holds and paths that it does not hold
- **WHEN** the proposal of a New item has a suspected block, and its `block_paths` are `src/sample.py:1`, `src/missing.py`, `../CONTEXT.md`, `/etc/hosts`, `src/sample.py` and `CONTEXT.md`, and the checkout holds `src/sample.py` and `CONTEXT.md`
- **THEN** the job record holds `refine.block_paths` `src/sample.py,CONTEXT.md`

#### Scenario: A proposal with no block
- **WHEN** the proposal of a New item gives `block_paths` `src/sample.py` and has no suspected block and no dependency
- **THEN** the job record holds no `refine.block_paths`

### Requirement: The next-step comment names the cited files
The comment that gives an item its next step SHALL end with a line that names each recorded file, when refine records a path for the item, and SHALL name no file when it records none.

#### Scenario: A comment for an item whose block cites code
- **WHEN** refine records `refine.block_paths` `src/sample.py,CONTEXT.md` for an item
- **THEN** the last line of refine's comment on the item names `src/sample.py` and `CONTEXT.md` as the files whose change on the default branch makes the next round look at the item again

#### Scenario: A comment for an item with no block
- **WHEN** refine records no `refine.block_paths` for an item
- **THEN** refine's comment on the item names no cited file

### Requirement: A change to the code that a block cites ends the wait
Without `--item`, `devops roadmap refine` SHALL look at an unchanged waiting item again when a commit on the default branch changed one of its recorded `refine.block_paths` at or after refine's last comment on the item. When no recorded path changed after that comment, the item SHALL keep waiting on its next step, and the round SHALL make no model call for it.

#### Scenario: The cited path changes after refine's last comment
- **WHEN** an item waits on an open blocker, or on a suspected block, with `refine.block_paths` `src/sample.py`, and a commit on the default branch changes `src/sample.py` five minutes after refine's last comment on the item
- **THEN** the next round refines the item again, with one model call, and the item is not waiting

#### Scenario: The cited path does not change after refine's last comment
- **WHEN** an item waits on an open blocker with `refine.block_paths` `src/sample.py`, the newest commit that changed `src/sample.py` is one day before refine's last comment, and a later commit changes only `CONTEXT.md`
- **THEN** the next round leaves the item waiting on its blocker and makes no model call

#### Scenario: The dry-run plan of a round
- **WHEN** `devops roadmap refine --dry-run` plans a round without `--item`, and when it plans a round with `--item 7`
- **THEN** the round's plan lists one read of the newest commit that changed each cited path of a waiting item, under the condition that no comment follows refine's last comment, and the plan with `--item` lists no such read

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

### Requirement: An open dependency that the proposal names blocks the item
`devops roadmap refine` SHALL give an item the next step `blocked` when its validated proposal names an open issue as a dependency. This applies when the proposal has no open question and fits one pull request. It SHALL record the open issues in `refine.blocked_by` and SHALL NOT set the Status to Ready. A Ready item SHALL go back to New. A closed dependency SHALL NOT hold the item back.

#### Scenario: A complete proposal with one open dependency
- **WHEN** a New item has a complete proposal with one open dependency (no open question, no split, no suspected block)
- **THEN** the next step is `blocked` with that issue, `refine.blocked_by` holds its number, and the item stays New

#### Scenario: A Ready item with an open dependency
- **WHEN** the proposal of a Ready item meets the same conditions, and a person runs refine for the item with `--item`
- **THEN** the item goes back to New, with the next step `blocked` and `refine.blocked_by` set

#### Scenario: A closed dependency
- **WHEN** a New item has a complete proposal with one closed dependency (no open question, no split, no suspected block)
- **THEN** the next step is `ready`, `refine.blocked_by` is empty, and the item is Ready

### Requirement: The last blocker to close ends the block
A blocked item SHALL wait while one of its recorded blockers is open, with no model call. The round after the last blocker closes SHALL refine the item again.

#### Scenario: The last blocker closes
- **WHEN** an item waits on two open dependencies, one of them closes, and then the other closes
- **THEN** the round after the first close leaves the item waiting on the second, with no model call. The round after the second close refines the item with one model call and sets it Ready

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

### Requirement: Refine reads a dependency that the body names by its title
Refine SHALL add to the dependencies of a proposal each issue that the Dependencies section of the body names by a quoted Conventional Commit title: the one open Item with that exact title, else the one closed Item with it. A list item that names `#N` SHALL name its issue by the number. A title that names no Item or two Items SHALL fail the round with the job check `dependencies`, and the error SHALL ask for `#<number>`.

#### Scenario: An open issue named by its title
- **WHEN** the Dependencies section names the quoted title of an open issue and the proposal names no dependency
- **THEN** the item has the next step `blocked` with that issue, and the refine section lists the issue under Dependencies

#### Scenario: A closed issue named by its title
- **WHEN** the Dependencies section names the quoted title of a closed issue
- **THEN** the item reaches Ready, and the refine section lists the issue under Dependencies

#### Scenario: A title that names no single issue
- **WHEN** the Dependencies section names a quoted title that no issue has, or that two open issues have
- **THEN** the item has the next step `retry`, `refine.failed_check` is `dependencies`, `refine.failure` names the title and asks for `#<number>`, and refine wrote no comment

#### Scenario: Quoted text that is no title, and an item with a number
- **WHEN** the Dependencies section holds a quoted tool name, and a list item that names `#N` and a title that no issue has
- **THEN** the round has no job failure

### Requirement: A person wait that older rules set gets one new look
A round that writes a proposal SHALL record `CONST_ROADMAP_REFINE_RULES_SINCE` as `refine.rules`. A round SHALL refine an unchanged item that waits on a person when its `refine.rules` is older than that constant, or, when the record holds none, when refine's last comment is older. A wait on a person that the current rules set SHALL stay.

#### Scenario: A wait from before the rules
- **WHEN** an item waits on a person since a refine comment older than the rules, its record holds no version, and its body is unchanged
- **THEN** the next round refines it and records the current version, and a round after it that gets the same question again makes no model call

#### Scenario: A wait with the current version
- **WHEN** an item waits on a person, and its record holds the current version while refine's comment is older than the rules
- **THEN** the next round leaves it waiting on a person and makes no model call

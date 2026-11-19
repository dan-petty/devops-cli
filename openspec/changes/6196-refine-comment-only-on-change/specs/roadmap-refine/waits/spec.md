## REMOVED Requirements

### Requirement: The next-step comment names the cited files
**Reason**: The refine section of the body holds the watched files, and a comment holds no content of the section (#6196).
**Migration**: The requirement "The refine section holds the result of the round" of `roadmap-refine/comments` holds the files under `### Watched files`, and the event line names that part.

## MODIFIED Requirements

### Requirement: A change to the code that a block cites ends the wait
Without `--item`, `devops roadmap refine` SHALL look at an unchanged waiting item again when a commit on the default branch changed one of its recorded `refine.block_paths` at or after the start of the wait: the later of refine's last comment on the item and `refine.repeated_at`. When no recorded path changed at or after that start, the item SHALL keep waiting on its next step, and the round SHALL make no model call for it.

#### Scenario: The cited path changes after refine's last comment
- **WHEN** an item waits on an open blocker, or on a suspected block, with `refine.block_paths` `src/sample.py`, and a commit on the default branch changes `src/sample.py` five minutes after refine's last comment on the item
- **THEN** the next round refines the item again, with one model call, and the item is not waiting

#### Scenario: The cited path does not change after refine's last comment
- **WHEN** an item waits on an open blocker with `refine.block_paths` `src/sample.py`, the newest commit that changed `src/sample.py` is one day before refine's last comment, and a later commit changes only `CONTEXT.md`
- **THEN** the next round leaves the item waiting on its blocker and makes no model call

#### Scenario: The dry-run plan of a round
- **WHEN** `devops roadmap refine --dry-run` plans a round without `--item`, and when it plans a round with `--item 7`
- **THEN** the round's plan lists one read of the newest commit that changed each cited path of a waiting item, under the condition that no reply follows the start of the wait, and the plan with `--item` lists no such read

#### Scenario: A cited path that changed before a round with no comment
- **WHEN** a commit changes the cited path of a waiting item, the look that it starts finds the same wait and posts no comment, and two more rounds run
- **THEN** the change gave one model call, and the item holds one refine comment

### Requirement: The exits of a wait need no comment read
A round SHALL end the wait of an item whose count of comments is the recorded one, with no read of its comments, when every recorded blocker is closed, when a commit on the default branch changed a recorded `refine.block_paths` path, or, for a wait on a person, when an issue or a path of `refine.wait_refs` closed or changed. Only a change at or after the later of `refine.commented_at` and `refine.repeated_at` SHALL count. The `updated_at` of the item SHALL NOT be part of the check.

#### Scenario: A blocker closes
- **WHEN** a recorded wait holds a blocker, and a person closes the blocker
- **THEN** the next round refines the item, and the `updated_at` of the item is the one it had before

#### Scenario: A cited path changes
- **WHEN** a recorded wait cites `src/sample.py`, and a commit changes that path five minutes after `refine.commented_at`
- **THEN** the next round refines the item, and the `updated_at` of the item is the one it had before

### Requirement: A new comment ends the saving
A round SHALL read the comments of an item that waits when its count of comments differs from the recorded one. A reply at or after the start of the wait, the later of refine's last comment and `refine.repeated_at`, SHALL end the wait. A comment that is no reply SHALL cost one read, and the round SHALL record the new count.

#### Scenario: A reply
- **WHEN** a person replies to the comment of an item that waits on a person with a recorded wait
- **THEN** the next round reads the comments of the item and refines it

#### Scenario: A comment of another job
- **WHEN** the alternatives job comments on an item with a recorded wait
- **THEN** the next round reads the comments of the item once and keeps it waiting, and the round after it reads none

### Requirement: A wait on a person ends when a cause that its text names ends
Without `--item`, `devops roadmap refine` SHALL look again at an unchanged item that waits on a person when an issue that the wait text names closed, or a file that it names changed on the default branch, at or after the start of the wait. The wait text SHALL be the Open questions, Suspected block and Watched files of the refine section and the replies that the rounds read. An issue that closed before, an issue of another repository and the item SHALL end no wait.

#### Scenario: A named issue closes after the comment
- **WHEN** an item waits on a person, an open question of its refine section asks about #12, and #12 closes after refine's last comment
- **THEN** the next round refines the item again

#### Scenario: A named issue closed before the comment
- **WHEN** an open question of the refine section names #12 and #12 closed before refine's last comment
- **THEN** the item keeps waiting and the round makes no model call

#### Scenario: A named file changes with no recorded block path
- **WHEN** an item waits on a person with no `refine.block_paths`, an open question of its refine section names `src/sample.py`, and a commit on the default branch changes that file after refine's last comment
- **THEN** the next round refines the item again

#### Scenario: A reply names the issue
- **WHEN** the refine section names no issue, a reply that the round read names #12, and #12 closes after refine's last comment
- **THEN** the next round refines the item again

### Requirement: A read of the comments of a waiting item is recorded
When a round reads the comments of an item that waits and finds no reply, `--confirm` SHALL record `refine.comments_seen` (the count of the listing), `refine.commented_at` (the time of refine's last comment) and `refine.wait_refs` (the issues, then the paths, that the wait text names). A round that finds the same values in the record SHALL write nothing for the item.

#### Scenario: A wait on a person that names an issue and a path
- **WHEN** an item waits on a person, an open question of its refine section names issue 3 and the path `src/sample.py`, and a round runs with `--confirm`
- **THEN** the job record holds `refine.comments_seen` `1`, `refine.commented_at` with the time of refine's comment, and `refine.wait_refs` `#3,src/sample.py`

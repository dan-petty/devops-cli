## MODIFIED Requirements

### Requirement: A change to the code that a block cites ends the wait
Without `--item`, `devops roadmap refine` SHALL look at an unchanged waiting item again when a commit on the default branch changed one of its recorded `refine.block_paths` at or after `refine.read_at` (or refine's last comment when absent). Otherwise the item SHALL keep waiting with no model call.

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
A round SHALL end the wait of an item whose count of comments equals `refine.comments_seen`, with no read of its comments, when blockers close or a recorded `refine.block_paths` or `refine.wait_refs` entry changes at or after `refine.read_at` (or `refine.commented_at` when absent). `updated_at` SHALL NOT count.

#### Scenario: A blocker closes
- **WHEN** a recorded wait holds a blocker, and a person closes the blocker
- **THEN** the next round refines the item, and the `updated_at` of the item is the one it had before

#### Scenario: A cited path changes
- **WHEN** a recorded wait cites `src/sample.py`, and a commit changes that path five minutes after `refine.commented_at`
- **THEN** the next round refines the item, and the `updated_at` of the item is the one it had before

### Requirement: A new comment ends the saving
A round SHALL read the comments of an item that waits when its count of comments differs from `refine.comments_seen`. A trusted reply made after the start of the wait (`refine.read_at`, else refine's last comment) SHALL end the wait. A comment that is no reply SHALL cost one read, and the round SHALL record the new count.

#### Scenario: A reply
- **WHEN** a person replies to the comment of an item that waits on a person with a recorded wait
- **THEN** the next round reads the comments of the item and refines it

#### Scenario: A comment of another job
- **WHEN** the alternatives job comments on an item with a recorded wait
- **THEN** the next round reads the comments of the item once and keeps it waiting, and the round after it reads none

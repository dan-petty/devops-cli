## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: A refused refine repeat starts the wait at its round
When the store refuses a comment of refine as a repeat, refine records the round read time in `refine.read_at`. The wait of the item SHALL start at `refine.read_at`, so a change of a cited path or a named issue before the round SHALL NOT end the wait again.

#### Scenario: One change of a cited path
- **WHEN** a commit changes the cited path of a waiting item, the new look finds the same wait, and two more rounds run
- **THEN** the item holds one refine comment, and the change gave one model call

#### Scenario: A second change
- **WHEN** a second commit changes the cited path after that round
- **THEN** the rounds after it make one more model call

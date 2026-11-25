## MODIFIED Requirements

### Requirement: Refine posts a comment only on a changed result
Refine SHALL post its comment only when the next step, the section without its `checked-at` line or the item that holds the frame differs from the round before, or when the round files a deferred part. Every written non-failed round SHALL record `refine.read_at` as the time at which it read the comments and SHALL write no `refine.repeated_at`.

#### Scenario: The same result after a reply
- **WHEN** a person replies and the next round finds the same question
- **THEN** the round posts no comment and records `refine.read_at`

#### Scenario: A changed next step
- **WHEN** a reply answers the question and the next round sets the item Ready
- **THEN** the round posts one event line, records `refine.read_at`, and leaves `refine.repeated_at` unset

#### Scenario: A changed section
- **WHEN** a reply gives another split and the next round finds the split step again
- **THEN** the round posts one event line

### Requirement: A round with no comment starts the wait
The wait SHALL start at `refine.read_at`, falling back to refine's last comment when absent. Trusted comments made after the start, excluding refine's own comments and other job comments, SHALL end the wait and reach the model alongside replies after refine's last comment. A stage return SHALL count from refine's last comment.

#### Scenario: A second reply after a round with no comment
- **WHEN** a person replies, the next round finds the same question, a later round runs, and then the person replies again
- **THEN** the later round keeps the item waiting with no model call, and the round after the second reply sends both replies to the model

#### Scenario: A reply while a round with no comment runs
- **WHEN** a person replies after a round read the comments and before it writes, and the round finds the same question
- **THEN** `refine.read_at` is the time of the read, and the next round sends the reply to the model

#### Scenario: A reply while a round that posts a comment runs
- **WHEN** a person replies at T+1, after the round read comments at T and before the round posts its comment at T+2
- **THEN** the next round ends the wait, sends the reply of T+1 to the model, and ignores refine's own comment of T+2

#### Scenario: A reply at or before the read time
- **WHEN** the only person reply after an earlier refine comment was made at or before the recorded `refine.read_at`
- **THEN** the next round keeps the item waiting and makes no model call

## ADDED Requirements

### Requirement: A failed round records no read time
A round that fails its job SHALL NOT record `refine.read_at` for the item, so replies read by that failed round stay unread for the next round.

#### Scenario: A reply read by a failed round is sent again
- **WHEN** a round reads a reply of a person and then fails its job
- **THEN** the job record holds no `refine.read_at` from the failed round and the next round sends that reply to the model

### Requirement: An item with no recorded read time uses refine's last comment
When an item's job record holds no `refine.read_at`, a round SHALL use refine's last comment as the start of the wait and SHALL record `refine.read_at` for that round.

#### Scenario: An item whose record holds only the earlier repeat time keeps its wait
- **WHEN** an item's job record holds `refine.repeated_at` and no `refine.read_at`
- **THEN** the round sends replies that follow refine's last comment and writes `refine.read_at`

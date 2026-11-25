# roadmap-refine/comments Specification

## Purpose
Refine writes the result of a round once, in its section of the body, and posts a short event comment only when that result changes, so no comment repeats the body and no unchanged round posts again.

## Requirements

### Requirement: The refine section holds the result of the round
The refine section of the body SHALL hold the open questions, Fit, the suspected block, the dependencies, the watched files under `### Watched files` and the new items of the deferred parts under `### Moved to new items`. It SHALL list the watched files sorted, so that the same paths in another order give the same section.

#### Scenario: Watched files in two orders and two new items
- **WHEN** the section is built from a proposal with a suspected block, the block paths `src/b.py` and `src/sample.py` in either order, and the new items 21 and 22
- **THEN** both orders give the same section, which ends with `### Watched files`, a sorted list of the two paths, and `### Moved to new items` with `#21, #22`

### Requirement: A refine comment is one event line
A refine comment SHALL name the next step and the parts of the refine section that hold it. It SHALL hold no content line of the section, no commit and no Status sentence.

#### Scenario: The section and the comment of one result
- **WHEN** the test builds the section and the comment of one result for each next step
- **THEN** no content line of the section and no commit is in the comment, the comment names the section `Proposed design`, and each part that it names is a heading of the section

#### Scenario: An open dependency
- **WHEN** a round finds an open dependency and no open question
- **THEN** the comment is `Next step: the open items close, or a person replies in a comment or edits the body. See Dependencies in the section Proposed design of the body.`

### Requirement: The refine frame names the section
The owner-question frame of refine SHALL name the parts of the refine section that hold its question in place of the question text. It asks only the first open question, so it SHALL name the first point of `Open questions`. It SHALL keep the options, the recommendation, the evidence and the hidden block with the hash of the question. The frames of stage and implement SHALL keep the question text.

#### Scenario: A question for a person
- **WHEN** a round leaves an open question for a person
- **THEN** the frame names `Open questions`, holds no text of the question, and its hidden hash is the `owner_question.hash` of the record

#### Scenario: Two open questions
- **WHEN** a round leaves two open questions for a person
- **THEN** the frame names the first point of `Open questions`, and its hidden hash is the hash of the first question

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

### Requirement: A frame moves when the item that holds it closes
Refine SHALL record as `refine.frame` the item whose comment holds the frame of the question that it asked. The wait SHALL end when the open item that holds that frame is another item, and the next round SHALL post the frame when no older open item asks the question.

#### Scenario: The holder of the frame closes
- **WHEN** an item links the frame of an older item and the older item closes
- **THEN** the next round of the item posts the frame with the same hash

### Requirement: The dry run names the gate of the comment
The dry run of `devops roadmap refine` SHALL show the refine comment under the condition that the result of the round changed since the round before.

#### Scenario: The plan of a round and of one item
- **WHEN** the request plan of a round and of `--item 7` is built
- **THEN** the comment request of each holds the condition text of `refine_changed`

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

### Requirement: Event of a changed deferred section
The comment step of refine SHALL post the event comment when the deferred items of the round differ from the recorded `RefineRecordKey.DEFERRED`, also when its text equals the comment of the round before.

#### Scenario: A second deferred change with no comment between
- **WHEN** the record holds deferred issue `#21`, the round files deferred issue `#22`, its event text equals the text of the round before, and no comment follows that text
- **THEN** the store posts one more event comment and the event comment holds no `#22`

### Requirement: Module docstring line limit of refine
Each line of the module docstring of `src/devops_cli/roadmap/refine/refine.py` MUST have at most 100 characters.

#### Scenario: The module docstring of refine
- **WHEN** a test inspects `devops_cli.roadmap.refine.refine.__doc__` line by line
- **THEN** every line has at most 100 characters

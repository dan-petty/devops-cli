## Purpose

Refine writes the result of a round once, in its section of the body, and posts a short event comment only when that result changes, so no comment repeats the body and no unchanged round posts again.

## ADDED Requirements

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
The owner-question frame of refine SHALL name the parts of the refine section that hold its question in place of the question text. It SHALL keep the options, the recommendation, the evidence and the hidden block with the hash of the question. The frames of stage and implement SHALL keep the question text.

#### Scenario: A question for a person
- **WHEN** a round leaves an open question for a person
- **THEN** the frame names `Open questions`, holds no text of the question, and its hidden hash is the `owner_question.hash` of the record

### Requirement: Refine posts a comment only on a changed result
Refine SHALL post its comment only when the next step, the section without its `checked-at` line or the item that holds the frame differs from the round before, or when the round files a deferred part. A round that posts no comment SHALL record its time as `refine.repeated_at`. A round that posts one SHALL clear it.

#### Scenario: The same result after a reply
- **WHEN** a person replies and the next round finds the same question
- **THEN** the round posts no comment and records `refine.repeated_at`

#### Scenario: A changed next step
- **WHEN** a reply answers the question and the next round sets the item Ready
- **THEN** the round posts one event line and clears `refine.repeated_at`

#### Scenario: A changed section
- **WHEN** a reply gives another split and the next round finds the split step again
- **THEN** the round posts one event line

### Requirement: A round with no comment starts the wait
A reply, an answer to a frame on another item and a stage return SHALL end a wait only when made at or after the later of refine's last comment and `refine.repeated_at`. The model SHALL read each reply since refine's last comment.

#### Scenario: A second reply after a round with no comment
- **WHEN** a person replies, the next round finds the same question, a later round runs, and then the person replies again
- **THEN** the later round keeps the item waiting with no model call, and the round after the second reply sends both replies to the model

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

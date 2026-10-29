## ADDED Requirements

### Requirement: The request holds the recorded check for alternatives
The proposal request and the investigation request of an item SHALL hold the key `alternatives`. For an item whose body holds the alternatives job's block and whose job record holds a verdict, it SHALL be an object with the verdict, the tool URL or null, the block, and the job's latest comment cut to `CONST_ROADMAP_REFINE_MAX_REPLY_TOKENS`. Otherwise it SHALL be null. The comment of the job SHALL NOT be one of the `replies`.

#### Scenario: A partly check
- **WHEN** refine plans an item whose job record holds the verdict `partly` and a tool, with the block in its body
- **THEN** the proposal request holds `alternatives` with that verdict, that tool and the text of the job's comment, and the `replies` hold no comment of the job

#### Scenario: No check
- **WHEN** refine plans an item with no block in its body
- **THEN** the request holds `alternatives` null

#### Scenario: A block that a person deleted
- **WHEN** the job record holds a verdict and the body holds no block
- **THEN** the request holds `alternatives` null

### Requirement: A covers verdict is a question that only a person answers
When the recorded check of an item has the verdict `covers`, refine SHALL add the question to adopt the tool or to keep the item with a reason. While no comment of a person follows the job's latest comment, the question SHALL be open with the mark of a question for a person. A comment of refine or of the job is no comment of a person. An item with an open question has the next step `PERSON`, and the Ready check SHALL NOT set it Ready. A `partly` or `none` check SHALL add no question.

#### Scenario: No reply yet
- **WHEN** refine plans a New item with a `covers` check and no comment of a person after the job's comment, and the model answers every other question
- **THEN** the item's next step is `PERSON`, the step comment lists the adopt-or-keep question naming the tool, and the item is not Ready

#### Scenario: Not answered by the model
- **WHEN** no person replied and the model gives a `decision` answer that names the question's number
- **THEN** the question is still open

#### Scenario: A reply and an answer
- **WHEN** a person replied after the job's comment and the proposal answers the question with a `decision`
- **THEN** the question is closed and refine sets the item Ready when every other rule holds

#### Scenario: A reply and no answer
- **WHEN** a person replied after the job's comment and no answer names the question
- **THEN** the question is open and the next step is `PERSON`

#### Scenario: A partly check
- **WHEN** refine plans an item with a `partly` check that otherwise meets every rule of the Ready check
- **THEN** refine sets the item Ready

### Requirement: A reply to a covers question is answered by the proposal
After a comment of a person follows the job's latest comment, the `covers` question SHALL join the numbered key questions of the request. It SHALL be open until an answer names its number, and an answer of kind `person` SHALL leave it open.

#### Scenario: A person answer
- **WHEN** a person replied after the job's comment and the model gives an answer of kind `person` that names the question
- **THEN** the question is open and the next step is `PERSON`

### Requirement: A new covering tool brings an item back to refine
Refine SHALL record the URL of the covering tool it asked about as `refine.alternatives_asked`, and SHALL clear the key when the recorded check does not cover. An open New or Ready item whose job record holds a `covers` verdict with a tool URL that differs from the key SHALL be selected in the next round, though its body is unchanged, and without a read of its comments. A Ready item so selected SHALL go back to New when the question stays open.

#### Scenario: A Ready item gets a covers check
- **WHEN** a Ready item that refine refined earlier gets a `covers` check
- **THEN** the next round selects it, and writes the question, the next step `PERSON` and Status New

#### Scenario: The same tool is found again
- **WHEN** a re-check finds the same covering tool and refine asked about it
- **THEN** a Ready item is not selected and a waiting item keeps its wait

#### Scenario: A waiting item and a new tool
- **WHEN** a New item waits on a person, no person replied, and a re-check records another covering tool
- **THEN** the next round refines the item

### Requirement: The hash of the body leaves out the job's block
The hash that refine records as `refine.body_hash` SHALL be the hash of the body outside the alternatives job's block and refine's section, as the check for an unchanged item computes it. The check before a write SHALL compare the hash of the whole body outside refine's section, so a block that the job wrote after refine read the body is kept.

#### Scenario: An item with a block reads as unchanged
- **WHEN** refine refines an item whose body holds the job's block, and the next round reads the item with no change
- **THEN** the item reads as unchanged and the round does not refine it

#### Scenario: The job writes a block during the round
- **WHEN** the job writes a block between the read and the write of refine
- **THEN** refine does not write the body, and the block stays

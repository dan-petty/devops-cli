# roadmap-refine/alternatives Specification

## Purpose
How refine uses the recorded check for alternatives: the request key, the covers question that only a person answers, and the replies that answer it.

## Requirements

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
When the recorded check of an item has the verdict `covers`, refine SHALL add the question to adopt the tool or to keep the item with a reason. While no comment of a person follows the job's latest comment, the question SHALL be open with the mark of a question for a person. A comment of a roadmap job is no comment of a person. An item with an open question has the next step `PERSON`, and the Ready check SHALL NOT set it Ready. A `partly` or `none` check SHALL add no question.

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

#### Scenario: The job left no comment
- **WHEN** the item holds a `covers` record and block, no comment of the job, and a person replied
- **THEN** the question is answered, and a `decision` answer that names it closes the question

#### Scenario: A comment of another job
- **WHEN** only a comment of the stage job or of intake follows the job's comment
- **THEN** the question is not answered

#### Scenario: A person answer
- **WHEN** a person replied after the job's comment and the model gives an answer of kind `person` that names the question
- **THEN** the question is open and the next step is `PERSON`

### Requirement: The request carries the replies that answer a covers question
The `alternatives` key SHALL hold `answers`: for a `covers` check, the replies of persons since the check (the newest `CONST_ROADMAP_REFINE_MAX_REPLIES`, each cut to `CONST_ROADMAP_REFINE_MAX_REPLY_TOKENS`), and for any other check an empty list.

#### Scenario: Refine commented after the reply
- **WHEN** a person answered the `covers` question, refine commented again, and a person made a later comment
- **THEN** the request holds the first reply in `alternatives.answers` and only the later comment in `replies`, and a `decision` answer closes the question

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

### Requirement: A rejected or in-use check adds no question
When the recorded check of an item has the verdict `rejected` or `in-use`, refine SHALL add no question, SHALL NOT set the next step `PERSON` because of the check, and SHALL NOT record `refine.alternatives_asked`. The request SHALL hold the verdict, the tool URL, the block and the job's latest comment of that check under the key `alternatives`, as for any check.

#### Scenario: A rejected check
- **WHEN** refine plans a New item whose recorded check has the verdict `rejected` and a tool, and the item otherwise meets every rule of the Ready check
- **THEN** the item has no open question and refine sets it Ready

#### Scenario: An in-use check
- **WHEN** refine plans a New item whose recorded check has the verdict `in-use` and a tool, and the item otherwise meets every rule of the Ready check
- **THEN** the item has no open question and refine sets it Ready

#### Scenario: The request
- **WHEN** refine plans an item whose recorded check has the verdict `rejected`
- **THEN** the proposal request holds `alternatives` with the verdict `rejected`, the tool URL and the text of the job's comment

### Requirement: A recorded verdict gates Ready
Refine SHALL set `status/ready` on an item only when its job record holds an `alternatives.verdict`, or when the alternatives check is off for the repository, and SHALL leave the item in `status/new` with the comment `Waiting for the alternatives check to run.` when the record holds no verdict and the check is on.

#### Scenario: An item with no verdict stays New
- **WHEN** Refine runs on an item whose job record holds no `alternatives.verdict` while the alternatives check is on for the repository
- **THEN** The item keeps `status/new` and refine writes the comment `Waiting for the alternatives check to run.`

#### Scenario: An item with a recorded verdict becomes Ready
- **WHEN** Refine runs on an item whose `alternatives.verdict` is `none`, `not-applicable`, `rejected` or `in-use` and every other readiness rule passes
- **THEN** Refine sets the item to `status/ready`.

#### Scenario: A repository whose check is off is exempt
- **WHEN** The repository is private, or it has no search provider, and the item holds no `alternatives.verdict`
- **THEN** Refine sets the item to `status/ready` when every other readiness rule passes.

### Requirement: A person's Ready label stays through a round
Refine SHALL leave a `status/ready` label that a person set on an item whose record holds no verdict, and SHALL write no other Status label on that item.

#### Scenario: A person's Ready label survives a round
- **WHEN** A person sets `status/ready` on an item with no `alternatives.verdict` and refine runs on the item
- **THEN** The item keeps `status/ready` and refine writes no other Status label.

### Requirement: The wait for a verdict ends when the check writes one
Refine SHALL keep an item whose gate fails on the wait `alternatives` with no comment read, and SHALL take the item again in the round after the alternatives check records a verdict.

#### Scenario: The recorded verdict ends the wait
- **WHEN** The alternatives check records an `alternatives.verdict` on an item that refine left on the `alternatives` wait
- **THEN** The next refine round takes the item and sets `status/ready` when every other readiness rule passes.

#### Scenario: The report names the wait of the item
- **WHEN** A round leaves an item on the `alternatives` wait and prints its refinement plan
- **THEN** The plan holds the heading of the `alternatives` wait and the line of the item under it.

### Requirement: The workflow document names the gate
The workflow document SHALL name the alternatives-verdict gate in step 2 of its eight steps.

#### Scenario: Step 2 names the gate
- **WHEN** A reader reads step 2 of the eight steps of the workflow document
- **THEN** The step text names the rule that refine sets Ready only with an `alternatives.verdict` or on a repository whose check is off.

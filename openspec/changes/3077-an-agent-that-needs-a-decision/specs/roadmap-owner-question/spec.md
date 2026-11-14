## Purpose
How a roadmap step asks the owner for a decision: one comment with the question, its options, a recommendation and the evidence, one frame for each question hash, and the answer of a trusted user that resumes the covered items.

## ADDED Requirements

### Requirement: A step posts one owner-question form
A roadmap step that needs an owner decision SHALL post one comment that holds the question once, two or three options with their results, a recommendation, the evidence and a hidden block with the question hash.

#### Scenario: A refine step asks a question
- **WHEN** A refine step needs an owner decision.
- **THEN** The comment holds the question text once, two or three options, a recommendation, at least one evidence link and a hidden block with the question hash.

### Requirement: One frame for each question hash
The job SHALL post one question frame for each question hash, on the oldest open item that asks it, and MUST link it from every other item that asks the same question.

#### Scenario: Two items ask the same question
- **WHEN** Two items ask a question with the same text and options.
- **THEN** One comment holds the frame on the older item, the second item gets a comment with a link to that frame, and no second frame exists.

### Requirement: One question in one run
A step SHALL ask at most one question in one run and SHALL end after it posts the frame.

#### Scenario: A step needs two decisions
- **WHEN** A step needs a second owner decision in the same run.
- **THEN** The step posts one frame, ends, and asks the second question only after the first answer resumes the item.

### Requirement: One form module for refine, stage and implement
Refine, stage and implement SHALL post the owner-question form through one module.

#### Scenario: The stage step asks a question
- **WHEN** A stage step needs an owner decision.
- **THEN** The stage step posts the same form as refine, with the same hash rule and the same hidden block.

### Requirement: A trusted reply resumes the covered items
A reply from a trusted author to an open owner-question frame SHALL resume every item covered by the frame, with the answer in the context of its run.

#### Scenario: The owner answers
- **WHEN** A trusted author who is no bot and not the account that the job acts as replies to an open frame.
- **THEN** A refine run starts for each covered item with the answer text and the frame reference in its context, and the job record of each covered item holds the question hash and the answer.

### Requirement: An untrusted reply starts no run
A reply from an author who is not trusted MUST NOT start a run.

#### Scenario: A stranger replies
- **WHEN** An author who is not trusted, or a bot, replies to an open frame.
- **THEN** No run starts, the frame stays open, and the inbox still lists it.

### Requirement: The open frame is the marker and no status label is added
The change MUST NOT add a status label, and the status family SHALL keep the six values of ADR 0016.

#### Scenario: The workflow label invariant runs
- **WHEN** The invariant test of the workflow document compares the labels file with the workflow document and the code.
- **THEN** The labels file and the code hold the same six status labels, and the workflow document names each one.

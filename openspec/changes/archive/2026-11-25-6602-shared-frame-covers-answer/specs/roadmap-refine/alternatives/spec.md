## MODIFIED Requirements

### Requirement: A reply to a covers question is answered by the proposal
After a comment of a person follows the job's latest comment, or a trusted person replies after the shared owner-question frame on the frame item named by `OwnerQuestion.link_comment`, the `covers` question SHALL join the numbered key questions of the request. It SHALL be open until an answer names its number, and an answer of kind `person` SHALL leave it open. Replies from a bot or the job account on the frame item SHALL NOT answer the question.

#### Scenario: The job left no comment
- **WHEN** the item holds a `covers` record and block, no comment of the job, and a person replied
- **THEN** the question is answered, and a `decision` answer that names it closes the question

#### Scenario: A comment of another job
- **WHEN** only a comment of the stage job or of intake follows the job's comment
- **THEN** the question is not answered

#### Scenario: A person answer
- **WHEN** a person replied after the job's comment and the model gives an answer of kind `person` that names the question
- **THEN** the question is open and the next step is `PERSON`

#### Scenario: Person answers on the shared frame item
- **WHEN** a linked item holds `OwnerQuestion.link_comment` pointing to a frame item, and a trusted person replies on the frame item after the frame
- **THEN** `covers_question` returns `answered=True` with that reply in `answers`

#### Scenario: Bot or job account replies on the frame item
- **WHEN** only a bot or the job account replies on the frame item after the shared frame
- **THEN** `covers_question` returns `answered=False` and no reply in `answers`

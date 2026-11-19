## MODIFIED Requirements

### Requirement: A recorded verdict gates Ready
Refine SHALL set `status/ready` on an item only when its job record holds an `alternatives.verdict`, or when the alternatives check is off for the repository, and SHALL leave the item in `status/new` with the event line `Next step: the alternatives check records a verdict.` when the record holds no verdict and the check is on.

#### Scenario: An item with no verdict stays New
- **WHEN** Refine runs on an item whose job record holds no `alternatives.verdict` while the alternatives check is on for the repository
- **THEN** The item keeps `status/new` and refine writes the event line `Next step: the alternatives check records a verdict.`

#### Scenario: An item with a recorded verdict becomes Ready
- **WHEN** Refine runs on an item whose `alternatives.verdict` is `none`, `not-applicable`, `rejected` or `in-use` and every other readiness rule passes
- **THEN** Refine sets the item to `status/ready`.

#### Scenario: A repository whose check is off is exempt
- **WHEN** The repository is private, or it has no search provider, and the item holds no `alternatives.verdict`
- **THEN** Refine sets the item to `status/ready` when every other readiness rule passes.

### Requirement: A covers verdict is a question that only a person answers
When the recorded check of an item has the verdict `covers`, refine SHALL add the question to adopt the tool or to keep the item with a reason. While no comment of a person follows the job's latest comment, the question SHALL be open with the mark of a question for a person. A comment of a roadmap job is no comment of a person. An item with an open question has the next step `PERSON`, and the Ready check SHALL NOT set it Ready. A `partly` or `none` check SHALL add no question.

#### Scenario: No reply yet
- **WHEN** refine plans a New item with a `covers` check and no comment of a person after the job's comment, and the model answers every other question
- **THEN** the item's next step is `PERSON`, the Open questions of its refine section hold the adopt-or-keep question naming the tool, the step comment names Open questions, and the item is not Ready

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

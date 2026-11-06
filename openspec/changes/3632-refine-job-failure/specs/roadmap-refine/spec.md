## RENAMED Requirements

- FROM: `### Requirement: Only a person's decision or an unsourced fact waits on a person`
- TO: `### Requirement: Only a person's decision waits on a person`

## MODIFIED Requirements

### Requirement: Only a person's decision waits on a person
A question of kind `person` SHALL be an open question with "(a person decides)", and the item SHALL wait on a person. An open question with no such mark SHALL NOT make an item wait on a person.

#### Scenario: A decision that AGENTS.md reserves for a person
- **WHEN** the proposal asks "Which repository secret holds the key?" as a `person` question and the proposal passes its form check
- **THEN** the item waits on a person, and the comment lists "Which repository secret holds the key? (a person decides)"

### Requirement: A stopped investigation keeps the first proposal
When the investigation stops with no proposal, refine SHALL keep the first proposal. When a question that is not marked "(a person decides)" is still open, refine SHALL record a job failure with the failed check `investigation_stopped` and the first line of the error, and SHALL NOT keep that question as a wait on a person.

#### Scenario: The investigation stops with no proposal
- **WHEN** the investigation asks for more tool calls than its budget holds, and the first proposal holds only a `(proposed)` decision
- **THEN** refine keeps the first proposal, and the item is not a failed item

#### Scenario: The output retries run out
- **WHEN** the investigation of an item with a `(missing verified source)` question stops with `Exceeded maximum output retries (2)`
- **THEN** the item has the next step `retry`, its job record names the check `investigation_stopped` and holds the error, and no comment lists the question

## ADDED Requirements

### Requirement: A form check failure is a job failure that retries
When the proposal fails a form check, refine SHALL write no body, no comment and no Status. It SHALL record the failed check names in `refine.failed_check` and the count of tries in `refine.tries`. While the count is below `CONST_ROADMAP_REFINE_MAX_TRIES`, it SHALL record the next step `retry`, and a later round SHALL refine the item again. The form checks are `problem_statement`, `existing_tool` and `acceptance_criteria`.

#### Scenario: A proposal with no problem statement
- **WHEN** the model returns a proposal whose problem statement is empty, and the item has no earlier try
- **THEN** the item has no person wait, `refine.next_step` is `retry`, `refine.tries` is `1`, `refine.failed_check` is `problem_statement`, and refine wrote no comment

#### Scenario: The next round tries again
- **WHEN** a round follows a failed try and nothing changed in the item
- **THEN** the round selects the item and sends one model request for it

### Requirement: A passing proposal clears the job failure
A proposal that passes the form checks with no job failure SHALL clear `refine.tries`, `refine.failed_check` and `refine.failure` from the job record.

#### Scenario: A later proposal passes
- **WHEN** the model returns a whole proposal after a failed try
- **THEN** the item is refined as before, and its record holds no `refine.tries`, `refine.failed_check` or `refine.failure`

### Requirement: A job failure at the try limit waits on a body edit
When the count of tries reaches `CONST_ROADMAP_REFINE_MAX_TRIES`, refine SHALL record the next step `failed`, and a round SHALL send no model request for the item until a person edits its body.

#### Scenario: The limit is reached
- **WHEN** a proposal fails the same form check on the third round and the limit is 3
- **THEN** `refine.next_step` is `failed`, `refine.tries` is `3`, and the next round sends no model request for the item

#### Scenario: A body edit
- **WHEN** a person edits the body of an item whose next step is `failed`
- **THEN** the next round selects the item, and its count of tries starts at 1

### Requirement: A source question is answered with the read tools or reports what they searched
When a question has no verified source after the investigation, refine SHALL treat it as a job failure with the failed check `missing_source`, and SHALL record in `refine.failure` the calls of the read tools that the investigation made. The item SHALL NOT wait on a person for it.

#### Scenario: A read tool finds the source
- **WHEN** the first proposal answers "Where is the sample function?" as a fact with no source, and the investigation reads `src/sample.py`
- **THEN** the item has no open question and no job failure

#### Scenario: No tool finds the source
- **WHEN** the investigation searches for a text that the repository does not hold and answers with no source
- **THEN** the item has the next step `retry`, `refine.failed_check` is `missing_source`, and `refine.failure` names the search call and its text

### Requirement: The report counts the items that go on without a person
The refine plan report SHALL show the number of items of the round whose next step is `ready`, `blocked` or `retry`, and SHALL list each one.

#### Scenario: A round with a Ready item, a person question and a retry
- **WHEN** a round refines one item to Ready, one item with a `(a person decides)` question and one item whose proposal fails a form check
- **THEN** the report states that 2 items go on without a person and lists the Ready item and the retry item

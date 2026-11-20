## ADDED Requirements

### Requirement: A form check failure names the criterion and the part
The failure that a form check records SHALL name each failed check and, for each failed acceptance criterion, the index of the criterion and the part that failed, such as `acceptance_criteria[0].then`.

#### Scenario: An empty then of the first criterion
- **WHEN** a round reads a proposal whose first acceptance criterion has an empty `then`
- **THEN** `refine.failure` holds `acceptance_criteria[0].then`

### Requirement: The next request carries the whole earlier failure
When the job record of the item holds `refine.failure`, the next proposal request SHALL carry that whole text in `judge_findings` beside the open findings of the review, and SHALL NOT cut it with a character cap.

#### Scenario: An empty then of the earlier try
- **WHEN** a round follows a try whose first criterion had an empty `then`
- **THEN** the request of the round holds the failure text, which names `acceptance_criteria[0].then`

#### Scenario: A long earlier failure
- **WHEN** a test calls `_judge_findings` with a job record whose form-check failure is longer than 2000 characters
- **THEN** the findings that the next request carries hold the whole text

### Requirement: No character cap cuts a refine failure
The refine code MUST NOT cut the text of a failure or of the review findings with a fixed character cap, and neither `CONST_ROADMAP_REFINE_FAILURE_MAX_CHARS` nor `CONST_ROADMAP_REFINE_JUDGE_FINDINGS_MAX_CHARS` SHALL exist.

#### Scenario: No cap constant
- **WHEN** a test reads the constants of the project
- **THEN** it finds neither `CONST_ROADMAP_REFINE_FAILURE_MAX_CHARS` nor `CONST_ROADMAP_REFINE_JUDGE_FINDINGS_MAX_CHARS`

## MODIFIED Requirements

### Requirement: A form check failure is a job failure that retries
When the proposal fails a form check, refine SHALL write no body, no comment and no Status. It SHALL record the failed check names in `refine.failed_check`, the count of tries in `refine.tries`, and the failure in `refine.failure`. Below `CONST_ROADMAP_REFINE_MAX_TRIES` it SHALL record the next step `retry`, and a later round SHALL refine the item again. The form checks are `problem_statement`, `existing_tool` and `acceptance_criteria`.

#### Scenario: A proposal with no problem statement
- **WHEN** the model returns a proposal whose problem statement is empty, and the item has no earlier try
- **THEN** the item has no person wait, `refine.next_step` is `retry`, `refine.tries` is `1`, `refine.failed_check` is `problem_statement`, and refine wrote no comment

#### Scenario: An empty part of a criterion
- **WHEN** the model returns a proposal whose first acceptance criterion has an empty `then`
- **THEN** the failure text in the record names `acceptance_criteria[0].then`, and refine wrote no comment

#### Scenario: The next round tries again
- **WHEN** a round follows a failed try and nothing changed in the item
- **THEN** the round selects the item and sends one model request for it

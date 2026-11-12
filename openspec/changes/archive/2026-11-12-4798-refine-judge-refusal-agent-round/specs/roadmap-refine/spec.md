## ADDED Requirements

### Requirement: A refusal of the review is a job failure that a later round fixes
A finding of the type `missing_path`, `false_premise`, `ignores_existing_code` or `spec_delta_wrong`, or a placeholder, with a quote that the input holds, SHALL be an open finding. With an open finding, refine SHALL keep the item New, record `refine.judge` `refused`, the failed check `judge_refused` and the open findings in `refine.judge_findings`, and write no comment. The next request SHALL give them as `judge_findings`. Another finding SHALL be advice.

#### Scenario: The review refuses
- **WHEN** the review finds a `false_premise` that quotes the problem statement, and a `contrived_test` with no quote
- **THEN** the item stays New, its job record holds `refine.judge` `refused`, `refine.next_step` `retry`, `refine.tries` `1`, `refine.failed_check` `judge_refused` and only the `false_premise` with its evidence in `refine.judge_findings`, and refine writes no comment

#### Scenario: The next round fixes the findings
- **WHEN** a round follows the refusal, and its review finds no open defect
- **THEN** its request holds the `false_premise` in `judge_findings`, the item is Ready with `refine.judge` `approved`, and the job record holds no `refine.tries` and no `refine.judge_findings`

#### Scenario: The third refusal
- **WHEN** the review refuses the same body of a bot item in three rounds
- **THEN** `refine.next_step` is `failed`, the next round makes no proposal call and no review call, and the inbox lists the item in the class `failed`

#### Scenario: A body edit after the third refusal
- **WHEN** a person edits the body after the third refusal
- **THEN** the next round makes one review call, and `refine.tries` starts at `1`

#### Scenario: A quote that the input does not hold
- **WHEN** the review finds a `false_premise` whose quote is in no text of the input
- **THEN** the item is Ready and its job record holds `refine.judge` `approved`

#### Scenario: A finding about tasks
- **WHEN** the review finds a `task_order` or a `verify_form` finding that quotes the input
- **THEN** the finding is advice, because a proposal holds no task group, and the item is Ready with `refine.judge` `approved`

### Requirement: The review keeps the approval of an unchanged body
Refine SHALL make no review call for an item that holds `refine.judge` `approved` with an unchanged body. A body edit SHALL end the approval, and the next round SHALL review the new proposal.

#### Scenario: An approved item that a round looks at again
- **WHEN** a round looks again at an item that holds `refine.judge` `approved`, and its body is unchanged
- **THEN** refine keeps the approval and makes no review call

#### Scenario: A body edit after a refusal
- **WHEN** a person edits the body after a refusal, and the review finds no open defect
- **THEN** the next round makes one review call and sets the item Ready

## MODIFIED Requirements

### Requirement: A round reviews a Ready item of a bot again when its approval ends
A round SHALL take a Ready item of a trusted bot when its approval does not hold. The approval does not hold when `refine.judge` is not `approved`, or when the body hashes differently from `refine.body_hash` and `refine.section_hash`. The round SHALL review the new proposal. With no open finding, the item SHALL stay Ready with a new approval. With an open finding, the item SHALL go back to New.

#### Scenario: A person edits the body of an approved item
- **WHEN** refine approved a Ready item of the Service App, and a person adds a line to the body outside the section of refine
- **THEN** the item has no approval that holds, the next round makes one proposal call and one review call, and the item stays Ready with a new approval

#### Scenario: The review refuses the edited body
- **WHEN** the review finds an open defect in the proposal for the edited body
- **THEN** the item goes back to New, its job record holds `refine.judge` `refused` and `refine.next_step` `retry`, and no job takes it

#### Scenario: An approval that holds
- **WHEN** a Ready item of the Service App holds `refine.judge` `approved` and its body is unchanged
- **THEN** a round does not take the item for this reason

### Requirement: A passing proposal clears the job failure
A proposal that passes the form checks with no job failure SHALL clear `refine.tries`, `refine.failed_check`, `refine.failure` and `refine.judge_findings` from the job record.

#### Scenario: A later proposal passes
- **WHEN** the model returns a whole proposal after a failed try
- **THEN** the item is refined as before, and its record holds no `refine.tries`, `refine.failed_check`, `refine.failure` or `refine.judge_findings`

## REMOVED Requirements

### Requirement: A refusal keeps the item New and lists each finding
**Reason**: A refusal no longer waits on a person. It is a job failure, and the next round refines the item again with the findings (#4798).
**Migration**: Read "A refusal of the review is a job failure that a later round fixes".

### Requirement: The review looks again only after the body changes
**Reason**: After a refusal, the next round reviews a new proposal on the same body. Only an approval of an unchanged body holds with no review call.
**Migration**: Read "The review keeps the approval of an unchanged body" and "A refusal of the review is a job failure that a later round fixes".

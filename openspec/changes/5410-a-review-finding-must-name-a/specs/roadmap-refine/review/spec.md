## MODIFIED Requirements

### Requirement: A refusal of the review is a job failure that a later round fixes
A finding of the type `missing_path`, `false_premise`, `ignores_existing_code` or `spec_delta_wrong`, or a placeholder, that quotes the input and names a place of the proposal or the issue SHALL be an open finding. With an open finding, refine SHALL keep the item New, record `refine.judge` `refused`, the failed check `judge_refused` and the open findings in `refine.judge_findings`, and write no comment. The next request SHALL give them as `judge_findings`. Another finding SHALL be advice.

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

#### Scenario: A finding on a key that the proposal does not have
- **WHEN** the review finds a `false_premise` that quotes the problem statement and names a task group as its place
- **THEN** the finding is advice, because a proposal holds no task group, and the item is Ready with `refine.judge` `approved`

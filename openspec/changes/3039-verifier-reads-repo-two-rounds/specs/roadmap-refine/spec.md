# Spec Delta

## MODIFIED Requirements

### Requirement: A refusal keeps the item New and lists each finding
A finding of the type `missing_path`, `false_premise`, `ignores_existing_code` or `spec_delta_wrong`, or a placeholder, with a quote that the input holds, SHALL be an open finding. With an open finding, refine SHALL keep the item New, record `refine.judge` `refused` and the next step `edit`, and write one comment that lists each open finding with its evidence. A finding that is not open SHALL be advice, and the comment SHALL NOT list it. The review SHALL run with no tool, and its prompt SHALL name no tool and no repair round.

#### Scenario: The review refuses
- **WHEN** the review finds a `false_premise` that quotes the problem statement, and a `contrived_test` with no quote
- **THEN** the item stays New, its job record holds `refine.judge` `refused` and `refine.next_step` `edit`, and refine's one comment lists the `false_premise` with its evidence and does not list the `contrived_test`

#### Scenario: A quote that the input does not hold
- **WHEN** the review finds a `false_premise` whose quote is in no text of the input
- **THEN** the item is Ready and its job record holds `refine.judge` `approved`

#### Scenario: A finding about tasks
- **WHEN** the review finds a `task_order` or a `verify_form` finding that quotes the input
- **THEN** the finding is advice, because a proposal holds no task group, and the item is Ready with `refine.judge` `approved`

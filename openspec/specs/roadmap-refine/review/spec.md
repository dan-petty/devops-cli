# roadmap-refine/review Specification

## Purpose
The review of a Ready refine proposal for an item of a bot: the plain client with no tool, the refusals that a later round fixes, and the approval of an unchanged body.

## Requirements

### Requirement: Refine reviews a Ready proposal for an item of a bot
When the proposal for an item whose author is the Service App's bot or `github-actions[bot]` is ready, refine SHALL send the issue and the proposal to the verification pass of the stage job, with the model of the task slot `ai.tasks.verification`, before it plans the deferred parts. With no open finding, refine SHALL set the item Ready and record `refine.judge` `approved`. Refine SHALL make no review call for an item of a person.

#### Scenario: The review approves
- **WHEN** the proposal for a New item of the Service App is ready, and the review finds no open defect
- **THEN** the item is Ready, its job record holds `refine.judge` `approved`, and the review made one call

#### Scenario: An item of the owner
- **WHEN** the proposal for a New item of the owner is ready
- **THEN** refine makes no review call, sets the item Ready and records no `refine.judge`

### Requirement: The review of refine runs with no tool
The review of an item SHALL run with a plain client that has no tool, and its prompt SHALL name no tool and no repair round, because only an agent run of the stage job reads the repository and repairs a plan.

#### Scenario: The prompt of the review
- **WHEN** refine builds the request of the review
- **THEN** the client has no tool, and the instructions of the review name no tool and no repair round

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

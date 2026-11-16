# Spec Delta

## MODIFIED Requirements

### Requirement: Refine reviews a Ready proposal for an item of a bot
When the proposal for an item whose author is the Service App's bot or `github-actions[bot]` is ready, refine SHALL send the issue and the proposal to the verification pass of the stage job, with the model of the task `ai.tasks.refine_review`, before it plans the deferred parts. With no open finding, refine SHALL set the item Ready and record `refine.judge` `approved`. Refine SHALL make no review call for an item of a person.

#### Scenario: The review approves
- **WHEN** the proposal for a New item of the Service App is ready, and the review finds no open defect
- **THEN** the item is Ready, its job record holds `refine.judge` `approved`, and the review made one call

#### Scenario: An item of the owner
- **WHEN** the proposal for a New item of the owner is ready
- **THEN** refine makes no review call, sets the item Ready and records no `refine.judge`

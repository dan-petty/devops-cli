## MODIFIED Requirements

### Requirement: The queue of each row
The queue SHALL be: for `intake`, the candidates of the round (decided, left and held); for `stage`, the open items that the stage filter names; for `fix_plan`, the open pull requests of the issue listing that hold `verdict/fix-plan`; for `refine`, the items that the selection orders before the rules of each item and the limit; for `alternatives`, the items that the check can take and has not checked.

#### Scenario: The stage selection counts the items that the filter names
- **WHEN** The store holds 4 open Ready items and the stage limit is 1.
- **THEN** The selection takes 1 item and its queue is 4.

#### Scenario: The refine selection counts the items that it orders
- **WHEN** The store holds 3 New items that refine can take and the limit is 1.
- **THEN** The selection takes 1 item and the queue of the plan is 3.

#### Scenario: The store counts the plans with the label from its listing
- **WHEN** The store holds 2 open pull requests with `verdict/fix-plan`, 1 closed pull request with it and 1 open pull request without it.
- **THEN** `labelled_pulls("verdict/fix-plan")` gives the 2 open ones.

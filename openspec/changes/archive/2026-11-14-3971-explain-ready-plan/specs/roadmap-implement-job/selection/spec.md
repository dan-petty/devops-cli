## ADDED Requirements

### Requirement: An open plan pull request that is ready for review names the merge wait
The implement job SHALL give the reason "Its plan pull request #<number> is ready for review and awaiting merge." when the pull request of the item is open, is not a draft, and is the stage plan pull request of the item. It SHALL keep "Its pull request #<number> is not an open draft." for a closed or merged pull request and for an implement pull request that left draft status.

#### Scenario: A plan that stage_ready marked ready
- **WHEN** the item records the pull request as `stage.pr`, the pull request is open, and it is not a draft
- **THEN** the reason names the plan pull request and the merge wait

#### Scenario: A closed plan pull request
- **WHEN** the plan pull request of the item is closed or merged
- **THEN** the reason keeps "is not an open draft"

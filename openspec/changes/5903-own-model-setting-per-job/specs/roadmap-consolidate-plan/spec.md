# Spec Delta

## MODIFIED Requirements

### Requirement: Two tool-less calls judge each shortlist
Each shortlist SHALL go through one function that takes the shortlist and its item texts and returns the verdict for each member. The model implementation SHALL make two tool-less `chat_structured` calls with the client of `ai.for_task("consolidate")`: a proposal, then a refutation that sees the proposal and the member bodies and returns kept, weakened (link-only) or dropped, with reasons. Only a kept group SHALL have a non-link action. The judge SHALL read the task `consolidate` and no task of another job.

#### Scenario: The refutation decides the group
- **WHEN** a test scripts a proposal and a refutation of each of the three verdicts
- **THEN** a kept group keeps its actions, a weakened group has the shape `link-only` with every action `link`, a dropped group is not in the plan, and the second request holds the proposal and the member bodies

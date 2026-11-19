## MODIFIED Requirements

### Requirement: A recorded verdict gates Ready
Refine SHALL set `status/ready` on an item only when its job record holds an `alternatives.verdict`, or when the alternatives check is off for the repository, and SHALL leave the item in `status/new` with the event line `Next step: the alternatives check records a verdict.` when the record holds no verdict and the check is on.

#### Scenario: An item with no verdict stays New
- **WHEN** Refine runs on an item whose job record holds no `alternatives.verdict` while the alternatives check is on for the repository
- **THEN** The item keeps `status/new` and refine writes the event line `Next step: the alternatives check records a verdict.`

#### Scenario: An item with a recorded verdict becomes Ready
- **WHEN** Refine runs on an item whose `alternatives.verdict` is `none`, `not-applicable`, `rejected` or `in-use` and every other readiness rule passes
- **THEN** Refine sets the item to `status/ready`.

#### Scenario: A repository whose check is off is exempt
- **WHEN** The repository is private, or it has no search provider, and the item holds no `alternatives.verdict`
- **THEN** Refine sets the item to `status/ready` when every other readiness rule passes.

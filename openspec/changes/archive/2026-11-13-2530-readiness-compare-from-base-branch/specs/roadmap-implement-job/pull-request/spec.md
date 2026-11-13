## ADDED Requirements

### Requirement: The watch stops the item on a merged or closed pull request
The implement job watch SHALL stop the item when the pull request is merged or closed without a merge, and MUST NOT report such a pull request as ready.

#### Scenario: Closed while the job runs
- **WHEN** the watch reads the pull request as closed and not merged
- **THEN** the watch stops the item with the reason "The pull request was merged or closed while the job ran."

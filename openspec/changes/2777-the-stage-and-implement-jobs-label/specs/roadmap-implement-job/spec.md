## ADDED Requirements

### Requirement: Implement job labels its pull request from the new title
The implement job SHALL add the `type/*` and `scope/*` labels that the new title gives, after it sets the title and the body of the pull request, and SHALL remove a `type/*` or `scope/*` label that the old title gave and the new title does not give.

#### Scenario: The new title gives a different scope
- **WHEN** The implement job sets a new title whose scope differs from the old title
- **THEN** The old `scope/*` label is removed and the new `scope/*` label is added

#### Scenario: The new title gives the same labels
- **WHEN** The implement job sets a new title whose type and scope match the old title
- **THEN** The pull request keeps its `type/*` and `scope/*` labels

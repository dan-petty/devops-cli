## MODIFIED Requirements

### Requirement: Planned item uses its plan pull request title
For a Planned item, the repair pass SHALL take the summary from the title of the plan pull request that the job record names, and SHALL make no model request.

#### Scenario: Planned item with a valid plan title
- **WHEN** a Planned item has an over-limit title and its plan pull request title is `docs(spec): plan #<issue> Add a title repair pass`
- **THEN** the new summary is `Add a title repair pass` and the model records no request

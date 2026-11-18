## ADDED Requirements

### Requirement: Full title in the intake summary
The intake failure summary SHALL name a candidate with the complete title that intake sent.

#### Scenario: A new candidate with a long title fails to file
- **WHEN** A unit test runs `intake_candidate` with `confirm=True` for a new candidate whose title is longer than 80 characters, and the store's `create_issue` raises `GitHubOperationError`
- **THEN** The test asserts the intake failure text contains the complete title and not the title cut to 80 characters

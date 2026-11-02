## ADDED Requirements

### Requirement: Released comment on each issue
The Service SHALL comment 'Released in <version>' on each closed issue in the changelog of a merged release pull request.

#### Scenario: Two issues in the changelog
- **WHEN** A release pull request whose changelog names two closed issues merges
- **THEN** Each of the two issues holds exactly one 'Released in <version>' comment

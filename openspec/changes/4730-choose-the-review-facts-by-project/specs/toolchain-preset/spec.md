## ADDED Requirements

### Requirement: The roadmap file holds a review table
`resolve_profile` SHALL accept the review table of the roadmap file of a repository, so a repository that sets `[review] tag_pattern` keeps a valid roadmap file for the implement job.

#### Scenario: A roadmap file with a review table
- **WHEN** A commit holds a roadmap file with the project table and the review table, and the review table names `tag_pattern = "release-*"`.
- **THEN** `resolve_profile` gives the preset of the project table with no error.

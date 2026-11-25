## ADDED Requirements

### Requirement: The roadmap file holds a review table
`resolve_profile` SHALL accept the `[review]` table in `.devops/roadmap.toml`, so a repository that configures `[review] tag_pattern` keeps a valid profile for the implement job.

#### Scenario: A roadmap file with a review table
- **WHEN** a commit holds `.devops/roadmap.toml` with `[project]` and `[review] tag_pattern = "release-*"`
- **THEN** `resolve_profile` returns the preset of `[project]` with no error

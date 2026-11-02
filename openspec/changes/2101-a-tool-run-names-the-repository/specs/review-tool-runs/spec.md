## ADDED Requirements

### Requirement: ToolRun repository_uri field
A ToolRun SHALL have a repository_uri field of type str | None that holds the repository URI of the checkout, read from git, with no credential in it.

#### Scenario: Remote with credentials
- **WHEN** a checkout has a remote whose URL contains user:password@
- **THEN** repository_uri holds the URL with the userinfo removed

#### Scenario: No remote
- **WHEN** a checkout has no remote configured
- **THEN** repository_uri is None

## ADDED Requirements

### Requirement: A network git child with no token fails at once only for the App
When the process acts as the GitHub App, holds no installation token that has not expired, and the mint fails, the process runner SHALL raise the error of the mint before it starts a git child that reaches a remote. For a person, such a child SHALL start with no `GH_TOKEN`. A lookup that finds no token SHALL NOT be kept, so the next call looks again.

#### Scenario: The App's mint fails
- **WHEN** the environment holds `not-a-pem-key` as the App's key and the process runner starts `git fetch origin`
- **THEN** it raises `GitHubUnauthenticatedError` that says the App has no installation token, and no child starts

#### Scenario: A person has no login
- **WHEN** no token resolves and the process runner starts `git fetch` two times
- **THEN** each child starts with no `GH_TOKEN`, and `gh auth token` runs before each of them

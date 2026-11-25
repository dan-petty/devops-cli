## ADDED Requirements

### Requirement: Open step requests non-author reviewers on new automated pull requests
When `open_or_update` creates a new draft pull request with `reviewers`, it SHALL exclude the pull request author and already-requested logins case-insensitively and request remaining reviewers via GitHub REST. Automated roadmap callers (`open_row`, `stage`, `implement`, and `roadmap step open`) SHALL pass the repository owner, and dry-run plans SHALL list that write.

#### Scenario: Bot opens a draft pull request
- **WHEN** `open_or_update` creates pull request 701 authored by `devops-cli-service[bot]` with `reviewers=("dan-petty",)` and no prior requested reviewers
- **THEN** the client sends `POST /repos/<repo>/pulls/701/requested_reviewers` with `{"reviewers": ["dan-petty"]}`

#### Scenario: Author matches reviewer or reviewer already requested
- **WHEN** `open_or_update` creates a draft pull request authored by `dan-petty` or already listing `dan-petty` in `requested_reviewers` with `reviewers=("dan-petty",)`
- **THEN** the step sends zero `requested_reviewers` requests

#### Scenario: Automated roadmap dry-run plans list reviewer requests
- **WHEN** `stage_requests` or `implement_requests` builds a dry-run write plan
- **THEN** the plan includes `POST https://api.github.com/repos/<owner>/<name>/pulls/<pull request>/requested_reviewers`

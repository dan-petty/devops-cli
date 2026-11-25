## ADDED Requirements

### Requirement: Template pull request requests the repository owner as reviewer
When row 9 of `devops repos onboard` holds a template pull request whose author differs from `ctx.options.repo.owner` and whose `requested_reviewers` does not include the owner, `--confirm` SHALL request a review from `ctx.options.repo.owner` through route `template-pull-reviewers` (`POST /repos/{repo}/pulls/{pull}/requested_reviewers`, `RouteOwner.TEMPLATE_PULL`). When the pull request author equals the repository owner, no `requested_reviewers` request SHALL be sent.

#### Scenario: Bot-authored template pull request requests owner review
- **WHEN** `devops repos onboard --confirm --only 9` creates the template pull request authored by `devops-cli-service[bot]` on `example-org/app`
- **THEN** `RouteWriter` sends `POST /repos/example-org/app/pulls/1/requested_reviewers` with `{"reviewers": ["example-org"]}`

#### Scenario: Owner-authored template pull request skips self-review
- **WHEN** `devops repos onboard --confirm --only 9` creates the template pull request authored by `example-org` on `example-org/app`
- **THEN** no request is sent to `POST /repos/example-org/app/pulls/1/requested_reviewers`

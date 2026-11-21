## MODIFIED Requirements

### Requirement: eval grades reads the bot pull requests of the window with one search
`devops roadmap eval grades` SHALL read the pull requests of the bot of `service.github_app.slug` that changed in the window, with their label events, head branch, state, draft flag and creation time, in one GraphQL search for each 100 pull requests. `--repo` SHALL put the repository in the search.

#### Scenario: The search of the window and the repository
- **WHEN** a person runs `devops roadmap eval grades --repo example/app` at 2026-11-09T12:00:00Z with the slug `example-bot`
- **THEN** the command sends one GraphQL search for `is:pr author:app/example-bot updated:>=2026-11-02T12:00:00Z repo:example/app`

#### Scenario: No slug
- **WHEN** `service.github_app.slug` is not set
- **THEN** the command sends no request to GitHub, and its text names `service.github_app.slug`

## ADDED Requirements

### Requirement: The implement row scores each drafted attempt by the forge state of its delivery
The report SHALL score the `drafted` lines of `implement` that name one pull request (`pull`) once, by that pull request: with n lines, a merge or an open pull request out of draft SHALL give 1 success and n - 1 failures, a close with no merge n failures, and a draft n lines in `drafts_pending`. A line with no `pull` SHALL take the newest delivery of its item. The verdicts and the rows SHALL count only the pull requests opened in the window. With no bot a `drafted` line SHALL count as written.

#### Scenario: Four drafted attempts
- **WHEN** the window holds `drafted` lines with no `pull` of items 7, 8, 9 and 10 and a `stopped` line of item 11, and the deliveries of 7 to 10 merged, are ready, closed with no merge, and are a draft
- **THEN** the implement row has 4 attempts, 2 successes and 1 draft pending

#### Scenario: No bot
- **WHEN** `service.github_app.slug` is not set and the window holds those lines
- **THEN** the implement row has 5 attempts and 4 successes

#### Scenario: Two Jobs on one pull request
- **WHEN** the window holds two `drafted` lines of item 7 that name one pull request, and it merged
- **THEN** the lines count 1 success and 1 failure

#### Scenario: Two pull requests of one item
- **WHEN** item 8 has a `drafted` line of a pull request that closed and one of a pull request that merged
- **THEN** the lines count 1 failure and 1 success

#### Scenario: A merged pull request, then a new draft
- **WHEN** item 9 has a `drafted` line of a pull request that merged and one of a new draft
- **THEN** the lines count 1 success and 1 draft pending

#### Scenario: A pull request opened before the window
- **WHEN** the only bot pull request of a repository was opened before the window
- **THEN** the report gives that repository no row

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
The report SHALL score each `implement` line with the result `drafted` by the delivery of its item, from the head branch: a delivery that merged, or that is open and out of draft, SHALL be a success, and one that closed with no merge a failure. A draft SHALL keep the line out of the attempts and in `drafts_pending`. The verdicts SHALL count only the pull requests opened in the window. With no bot a `drafted` line SHALL count as the line says.

#### Scenario: Four drafted attempts
- **WHEN** the window holds `drafted` lines of items 7, 8, 9 and 10 and a `stopped` line of item 11, and the deliveries of 7 to 10 merged, are ready, closed with no merge, and are a draft
- **THEN** the implement row has 4 attempts, 2 successes and 1 draft pending

#### Scenario: No bot
- **WHEN** `service.github_app.slug` is not set and the window holds those lines
- **THEN** the implement row has 5 attempts and 4 successes

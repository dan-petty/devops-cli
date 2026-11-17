# review-pr-comment Specification

## Purpose
What the pull request comment of a review holds, so that it states only what the review ran.

## Requirements

### Requirement: A review comment names no persona
The pull request comment of a review SHALL name the files it checked and the analyzers that ran. It SHALL NOT name a persona, in a `Personas:` line or in a `Review by` heading, because no review stage runs a persona. The model notes of each result SHALL follow one another under one `Model Notes (Not Verified)` heading.

#### Scenario: A review with no findings
- **WHEN** a review with no findings formats its comment
- **THEN** the comment names the files and the analyzers, and has no `Personas:` line

#### Scenario: A review with findings
- **WHEN** a review with findings formats its comment
- **THEN** the findings follow the `AI Code Review` heading, and the comment has no `Review by` heading

### Requirement: One review comment for each head commit
`devops review pr --post` SHALL open its comment with the line `<!-- devops review pr: <head> -->`, where `<head>` is the full head commit of the pull request. It SHALL read the comments of the pull request first. A comment that holds the line of the same head SHALL be edited, or left as it is when it already holds the same review, and no second comment SHALL be posted. With no such comment, the command SHALL post a new comment, and the comment of an older head SHALL stay.

#### Scenario: A rerun on the same head
- **WHEN** the pull request holds the review comment of its head with another review, and the user runs `devops review pr --post` again
- **THEN** the command edits that comment and posts no comment

#### Scenario: The same review on the same head
- **WHEN** the pull request holds the review comment of its head with the same review
- **THEN** the command sends no write

#### Scenario: A new head
- **WHEN** the pull request holds the review comment of an older head, and the user runs `devops review pr --post` on a new head
- **THEN** the command posts a new comment that names the new head, and the comment of the older head stays

### Requirement: The dry run of the review comment lists the read and both writes
`devops review pr --post --dry-run` SHALL list the read of the comments of the pull request, then the change of the comment and the new comment, each with its condition, and SHALL make no request.

#### Scenario: Dry run with post
- **WHEN** the user runs `devops review pr --post --dry-run`
- **THEN** the plan lists the `GET` of the comments, the `PATCH` of the comment and the `POST` of a new comment, and GitHub receives no request

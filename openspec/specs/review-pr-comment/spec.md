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
`devops review pr --post` SHALL open its comment with `<!-- devops review pr: <head> -->`, with `<head>` as the head commit. It SHALL read the pull request comments first. An existing comment with that line and whose author equals the GitHub session login SHALL be edited in place, or left unchanged when identical. With no such comment, the command SHALL post a new comment, and comments of an older head or another author SHALL stay.

#### Scenario: A rerun on the same head
- **WHEN** the pull request holds the review comment of its head with another review, and the user runs `devops review pr --post` again
- **THEN** the command edits that comment and posts no comment

#### Scenario: The same review on the same head
- **WHEN** the pull request holds the review comment of its head with the same review
- **THEN** the command sends no write

#### Scenario: A new head
- **WHEN** the pull request holds the review comment of an older head, and the user runs `devops review pr --post` on a new head
- **THEN** the command posts a new comment that names the new head, and the comment of the older head stays

#### Scenario: Another author's head marker is left unchanged
- **WHEN** the pull request has a comment with the head marker whose author login is not the session login, and no comment of the session login holds that marker
- **THEN** `post_pr_review_comment()` creates a new review comment and does not update the other author's comment

#### Scenario: Own head review comment is edited
- **WHEN** the pull request has a head-marker comment of the session login with a different body
- **THEN** `post_pr_review_comment()` calls `update_issue_comment` with that comment id and creates no new comment

### Requirement: The dry run of the review comment lists the read and both writes
`devops review pr --post --dry-run` SHALL list the read of the comments of the pull request, then the change of the comment and the new comment, each with its condition, and SHALL make no request.

#### Scenario: Dry run with post
- **WHEN** the user runs `devops review pr --post --dry-run`
- **THEN** the plan lists the `GET` of the comments, the `PATCH` of the comment and the `POST` of a new comment, and GitHub receives no request

# review-pr-comment Specification

## MODIFIED Requirements

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

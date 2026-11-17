## ADDED Requirements

### Requirement: A pull request holds one conflict comment
The `comment_conflict` step SHALL keep one conflict comment on a pull request. The marker `<!-- devops roadmap pr_conflicts -->` SHALL be the only key of the comment. When the pull request holds a comment with the marker, the step SHALL edit that comment in place with the text of the current head, and SHALL post no second comment. The step SHALL post a comment only when no comment of the pull request holds the marker.

#### Scenario: The first conflict
- **WHEN** a person pull request that holds no conflict comment has a merge conflict
- **THEN** the row posts one conflict comment that names the base branch and the head commit

#### Scenario: A conflict at a new head
- **WHEN** the pull request holds the conflict comment of an older head and has a conflict at a new head
- **THEN** the row edits that comment with the new head and posts no comment

## MODIFIED Requirements

### Requirement: A conflict gets one comment
When GitHub reports a merge conflict for a delivery pull request, the pull request SHALL hold one conflict comment that names the default branch and the head commit. A conflict at a new head commit SHALL edit that comment in place with the new head, and SHALL post no second comment.

#### Scenario: A dirty mergeable state
- **WHEN** the read returns `mergeable` false with `mergeable_state` `dirty`
- **THEN** the row posts the conflict comment on the pull request and none on the issue

#### Scenario: The conflict persists
- **WHEN** the row runs twice and both reads report the conflict at the same head commit
- **THEN** the pull request holds one conflict comment

#### Scenario: A new head commit
- **WHEN** the second read reports the conflict at a new head commit
- **THEN** the row edits the conflict comment so that it names the new head commit, and the pull request holds one conflict comment

## REMOVED Requirements

### Requirement: A conflict that returns gets the comment again
**Reason**: A second comment with the same advice is duplicate content on the pull request (#6193, #6199).
**Migration**: The requirement "A conflict gets one comment" holds the rule: the one conflict comment names the current head.

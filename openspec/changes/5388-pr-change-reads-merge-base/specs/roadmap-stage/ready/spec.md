## ADDED Requirements

### Requirement: Jev reads the diff of a stage draft from the compare of its base branch
The diff in the request of the Jev completeness check SHALL be the compare of the base branch of the draft and its head commit. The row MUST NOT read the diff of the pulls endpoint and MUST NOT compare from the payload `base.sha`, because GitHub can keep a stale `base.sha` after the merge base moved.

#### Scenario: A stale base sha
- **WHEN** the payload `base.sha` of a green draft is not the merge base, and the compare from it holds the files of another change
- **THEN** the request to Jev holds the diff of the compare of the base branch and the head commit, and the round reads no diff of the pulls endpoint

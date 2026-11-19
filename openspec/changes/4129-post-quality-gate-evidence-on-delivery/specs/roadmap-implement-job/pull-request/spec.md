## ADDED Requirements

### Requirement: The job publishes the evidence before it marks the pull request ready
When `draft_readiness` answers ready for the implement pull request, the job SHALL publish the evidence of the head commit with the existing evidence publisher, and SHALL run `gh pr ready` only after the publisher writes the comment. When the publisher fails, the job SHALL stop the item before `gh pr ready`, leave the pull request a draft and set the Status to Blocked.

#### Scenario: Checks pass and the evidence posts
- **WHEN** the checks of the delivery pull request settle with a ready result
- **THEN** the job posts the evidence comment and then runs `gh pr ready` once

#### Scenario: The publisher fails
- **WHEN** the evidence publisher raises a Git Hub operation error
- **THEN** the item is Blocked, the pull request stays a draft, and `gh pr ready` ran never

#### Scenario: The evidence comment exists already
- **WHEN** the pull request holds an evidence comment from the job's own login
- **THEN** the publisher updates that comment and posts no second comment

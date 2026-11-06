## MODIFIED Requirements

### Requirement: The job rewrites the pull request after the push
After the push the job SHALL build the body of the pull request with `build_body` and set it, in this order: the why of the `proposal.md`, the line `Closes #N`, and the line `Change: openspec/changes/archive/<date>-<change>/` with the archive folder in a code span. The why SHALL be on one line, with a handle or a link of another repository in a code span, and SHALL fit in the 1,000 characters that the body limit leaves for the three parts. When the why is longer, is missing, or holds a closing keyword, the title of the issue SHALL stand in. The job SHALL NOT cut the why. The job SHALL post the outcome of each step as one comment on the pull request, and SHALL put nothing of it in the body.

#### Scenario: The body
- **WHEN** the job finishes the change of item 7
- **THEN** the body of the pull request starts with the why of the proposal, holds `Closes #7` before the `Change:` line, and ends with the `Change:` line of the archive folder, and `body_problems` finds no problem

#### Scenario: A long why is not cut
- **WHEN** the Why of the archived proposal is longer than the room that the body limit leaves
- **THEN** the body holds the title of the issue as its why, and holds no `...`

#### Scenario: A refused body stops the item
- **WHEN** `build_body` refuses the body, for a title of the issue that is a placeholder
- **THEN** the job stops the item at the step `pull request`, makes no `PATCH` of the pull request, and the stop comment names the problem

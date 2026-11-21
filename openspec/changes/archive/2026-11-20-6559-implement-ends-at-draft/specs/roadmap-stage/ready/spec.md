## MODIFIED Requirements

### Requirement: One function decides, and one function marks
`draft_readiness` SHALL be the only function that decides whether a recorded draft is marked. The row SHALL mark with `mark_ready`, the function that the ready path of the step `fix-checks` uses for a delivery draft, and SHALL record `stage.ready` with the number of the pull request, so that no later round reads it.

#### Scenario: The implement job and the row mark the same way
- **WHEN** the ready path of the step `fix-checks` and the row each mark a pull request ready
- **THEN** both run `gh pr ready <number> --repo <repo>`

#### Scenario: The decision is replaced
- **WHEN** a test replaces `draft_readiness` in `stage_ready` with a function that answers refuse
- **THEN** the round marks no pull request

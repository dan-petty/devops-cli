## ADDED Requirements

### Requirement: The check reads the head commit that the pull request names
`devops roadmap plan-check` SHALL fetch the head commit of the pull request by its SHA and SHALL read the tree of that commit. It SHALL NOT read `FETCH_HEAD`, which every worktree of the checkout shares with any other fetch.

#### Scenario: A moved pull ref
- **WHEN** `refs/pull/<number>/head` moves to another commit after the pull request facts name the head
- **THEN** the check reads the tree of the named head and reports the plan problems of that tree

#### Scenario: A parallel fetch
- **WHEN** another process fetches in a worktree of the same checkout between the fetch and the read
- **THEN** the check reads the tree of the named head

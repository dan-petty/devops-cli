## MODIFIED Requirements

### Requirement: One mark-ready wrapper
The ready step SHALL be the single wrapper executing `gh pr ready`. It SHALL ask `draft_readiness` before it sends `gh pr ready`, and it SHALL verify that the remote head commit matches the expected head before transitioning.

#### Scenario: Head matches expected head
- **WHEN** `draft_readiness` answers ready and the remote pull request head SHA equals the expected head SHA
- **THEN** `mark_ready` transitions the draft to ready

## ADDED Requirements

### Requirement: The wrapper sends nothing that draft readiness refuses
`mark_ready` SHALL judge the draft that its caller gives, or, when the caller gives none, the draft that `read_ready_draft` reads with the check runs of the head. When `draft_readiness` does not answer ready, it SHALL raise an error with the reason and SHALL send no `gh pr ready`. Only the `--force` of a person SHALL skip the decision.

#### Scenario: An implement draft with an unticked task group
- **WHEN** a caller gives an implement draft whose task group 5 has a task that is not ticked
- **THEN** `mark_ready` raises an error that names the group and sends no `gh pr ready`

#### Scenario: A caller with no draft
- **WHEN** a caller gives no draft for a green implement pull request whose task group 5 is not ticked
- **THEN** `mark_ready` reads the pull request, the check runs of its head and its change, raises an error that names the group, and sends no `gh pr ready`

#### Scenario: The force of a person
- **WHEN** a person passes `--force`
- **THEN** `mark_ready` sends `gh pr ready` with no decision

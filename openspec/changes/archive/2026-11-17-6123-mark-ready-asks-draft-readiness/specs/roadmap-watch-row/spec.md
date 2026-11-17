## ADDED Requirements

### Requirement: The watch row marks a plan draft ready only when draft readiness allows it
For a green bot draft that an item records as `stage.pr`, the watch row SHALL read the draft with `read_ready_draft` and SHALL mark it ready only when `draft_readiness` answers ready. The kind of the draft SHALL come from the record, so a pull request that the item records as `stage.pr` and as `implement.pr` is judged as its delivery. The row SHALL keep a refused head in the ledger field `ready_head` and SHALL judge that head once.

#### Scenario: A delivery on the plan branch with an unticked task group
- **WHEN** an item records one green draft as `stage.pr` and as `implement.pr`, and task group 5 of its change has a task that is not ticked
- **THEN** two rounds of the row send no `gh pr ready` and record no `stage.ready`

#### Scenario: A green plan draft that the decision allows
- **WHEN** an item records a green bot draft as `stage.pr` and `draft_readiness` answers ready
- **THEN** the row marks it ready and records `stage.ready`

## ADDED Requirements

### Requirement: An open dependency that the proposal names blocks the item
`devops roadmap refine` SHALL give an item the next step `blocked` when its validated proposal names an open issue as a dependency. This applies when the proposal has no open question and fits one pull request. It SHALL record the open issues in `refine.blocked_by` and SHALL NOT set the Status to Ready. A Ready item SHALL go back to New. A closed dependency SHALL NOT hold the item back.

#### Scenario: A complete proposal with one open dependency
- **WHEN** a New item has a complete proposal with one open dependency (no open question, no split, no suspected block)
- **THEN** the next step is `blocked` with that issue, `refine.blocked_by` holds its number, and the item stays New

#### Scenario: A Ready item with an open dependency
- **WHEN** the proposal of a Ready item meets the same conditions, and a person runs refine for the item with `--item`
- **THEN** the item goes back to New, with the next step `blocked` and `refine.blocked_by` set

#### Scenario: A closed dependency
- **WHEN** a New item has a complete proposal with one closed dependency (no open question, no split, no suspected block)
- **THEN** the next step is `ready`, `refine.blocked_by` is empty, and the item is Ready

### Requirement: The last blocker to close ends the block
A blocked item SHALL wait while one of its recorded blockers is open, with no model call. The round after the last blocker closes SHALL refine the item again.

#### Scenario: The last blocker closes
- **WHEN** an item waits on two open dependencies, one of them closes, and then the other closes
- **THEN** the round after the first close leaves the item waiting on the second, with no model call. The round after the second close refines the item with one model call and sets it Ready

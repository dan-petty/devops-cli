# roadmap-dependency-cycle

## ADDED Requirements

### Requirement: Refine reads blocker state from the open listing
A refine round SHALL decide whether each recorded blocker is open from the open listing that the round holds, and MUST make no `store.item` read for a blocker number.

#### Scenario: Blocked items with recorded blockers
- **WHEN** a refine round runs over blocked items whose `refine.blocked_by` records blocker numbers, against a store that counts each `item` call
- **THEN** the round records the blockers that the open listing holds and the store counts no `item` call for a blocker number

### Requirement: Stage and implement read dependency state from the open listing
`open_issue_dependencies` SHALL take the open item numbers of the listing and MUST make no `store.item` read for a dependency number.

#### Scenario: Stage or implement over an item with recorded dependencies
- **WHEN** a stage or implement round calls `open_issue_dependencies` with the open numbers and a store that counts each `item` call
- **THEN** the call returns the open dependencies from those numbers and the store counts no `item` call for a dependency number

### Requirement: An open blocker that is no Item stays no blocker
A recorded blocker number that the open listing does not hold MUST give no blocker, even when its issue is open.

#### Scenario: Open issue with no priority label
- **WHEN** the open listing holds no item for a recorded blocker number and the store would return an open item for that number
- **THEN** the round reports no open blocker for that number and the store counts no `item` call for it

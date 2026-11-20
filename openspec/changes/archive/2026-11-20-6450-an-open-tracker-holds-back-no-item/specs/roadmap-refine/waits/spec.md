## MODIFIED Requirements

### Requirement: An open dependency outside a cycle blocks the item
`devops roadmap refine` SHALL give an item the next step `blocked` when its validated proposal has no open question, fits one pull request and names a dependency that gives an open blocker (the rule of `roadmap-dependency-cycle`), and no dependency leads back to the item. It SHALL record the open blockers and SHALL NOT set the Status to Ready. A Ready item SHALL go back to New. A closed dependency and the parent tracker SHALL NOT hold the item back.

#### Scenario: A complete proposal with one open dependency
- **WHEN** a New item has a complete proposal with one open dependency (no open question, no split, no suspected block)
- **THEN** the next step is `blocked` with that issue, the refine record holds its number, and the item stays New

#### Scenario: A Ready item with an open dependency
- **WHEN** the proposal of a Ready item meets the same conditions, and a person runs refine for the item with `--item`
- **THEN** the item goes back to New, with the next step `blocked` and its number in the refine record

#### Scenario: A closed dependency
- **WHEN** a New item has a complete proposal with one closed dependency (no open question, no split, no suspected block)
- **THEN** the next step is `ready`, the refine record holds no blocker, and the item is Ready

#### Scenario: The parent tracker as the one dependency
- **WHEN** a New item has a complete proposal whose one dependency is the open parent tracker of the item
- **THEN** the next step is `ready`, the refine record holds no blocker, and the item is Ready

#### Scenario: Another tracker as the one dependency
- **WHEN** a New item has a complete proposal whose one dependency is another open tracker with the open sub-issues B and C
- **THEN** the next step is `blocked` with `#B` and `#C`, and the refine record holds `B,C`

### Requirement: The last blocker to close ends the block
A blocked item SHALL wait while the issues that its record names give an open blocker (the rule of `roadmap-dependency-cycle`), with no model call. The round after the last blocker closes, or after the last recorded issue stops being a blocker, SHALL refine the item again. A recorded issue that is now the parent tracker of the item SHALL end the wait, and a recorded issue that is now another tracker SHALL give the wait its open sub-issues. `devops roadmap explain` SHALL give the same wait.

#### Scenario: The last blocker closes
- **WHEN** an item waits on two open dependencies, one of them closes, and then the other closes
- **THEN** the round after the first close leaves the item waiting on the second, with no model call. The round after the second close refines the item with one model call and sets it Ready

#### Scenario: The recorded blocker is now the parent tracker
- **WHEN** a round recorded the item as blocked on an open issue, and that issue is now the parent tracker of the item
- **THEN** `refine_left_out` gives no wait, and the next round refines the item and sets it Ready

#### Scenario: The recorded blocker is now another tracker
- **WHEN** a round recorded the item as blocked on an open issue, and that issue is now a tracker with the open sub-issues B and C
- **THEN** the next round leaves the item waiting on `#B` and `#C` with no model call, and `refine_left_out` names `#B, #C`

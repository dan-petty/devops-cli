## ADDED Requirements

### Requirement: An open tracker holds back no Ready item
The stage job SHALL decide the open blockers that the Dependencies section of a Ready item names with the rule of `roadmap-dependency-cycle`. The open parent tracker of the item, and each open tracker above it, SHALL NOT leave the item out. Another open tracker SHALL leave the item out with the reason that names its open sub-issues.

#### Scenario: The Dependencies section names the parent tracker
- **WHEN** the Dependencies section of a Ready item names its open parent tracker
- **THEN** the job stages the item

#### Scenario: The Dependencies section names another tracker
- **WHEN** the Dependencies section of a Ready item names another open tracker with the open sub-issue B
- **THEN** the job leaves out the item, and the reason names `#B` and not the tracker

## MODIFIED Requirements

### Requirement: The stage selection leaves out an item with an open recorded blocker
The stage selection SHALL leave out an item whose `refine.blocked_by` record names an issue that gives an open blocker (the rule of `roadmap-dependency-cycle`). The reason SHALL name each open blocker. A recorded parent tracker of the item SHALL NOT leave it out.

#### Scenario: The recorded blocker is open
- **WHEN** an item's job record holds `refine.blocked_by` with #3308, and #3308 is open
- **THEN** the stage selection leaves out the item, and the reason names #3308

#### Scenario: The recorded blocker is closed
- **WHEN** an item's job record holds `refine.blocked_by` with #3308, and #3308 is closed
- **THEN** the stage selection does not leave out the item for that record

#### Scenario: The recorded blocker is the parent tracker
- **WHEN** an item's job record holds `refine.blocked_by` with the number of its open parent tracker
- **THEN** the stage selection does not leave out the item for that record

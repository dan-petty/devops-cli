## ADDED Requirements

### Requirement: The job returns an item whose premise needs an open plan
The stage job SHALL return an item to New when a cited path is missing at the staging commit and an open plan creates it. The stage job SHALL record each such open item in `refine.blocked_by` of the item. The stage job SHALL plan no change for the returned item. The stage job SHALL make no model call for the returned item.

#### Scenario: A missing path that an open plan creates
- **WHEN** the issue cites `src/devops_cli/roadmap/stage_constants.py`, the staging commit lacks it, and open item #3308 has a plan on the default branch whose `tasks.md` marks that path `(new)`
- **THEN** the stage job records #3308 in `refine.blocked_by` of the item, sets the item to New, and plans no change for it

#### Scenario: No model call for the returned item
- **WHEN** the premise probe of an item finds a dependency on an open plan
- **THEN** the stage job makes no model call for that item

### Requirement: The stage selection leaves out an item with an open recorded blocker
The stage selection SHALL leave out an item whose `refine.blocked_by` record names an open item. The reason SHALL name each open item.

#### Scenario: The recorded blocker is open
- **WHEN** an item's job record holds `refine.blocked_by` with #3308, and #3308 is open
- **THEN** the stage selection leaves out the item, and the reason names #3308

#### Scenario: The recorded blocker is closed
- **WHEN** an item's job record holds `refine.blocked_by` with #3308, and #3308 is closed
- **THEN** the stage selection does not leave out the item for that record

### Requirement: The stage check refuses an overlapping create path
The stage check SHALL refuse a plan that lists a path in `creates` that another open plan also creates. The problem SHALL name the path and the open item. The reply SHALL go back to the model once.

#### Scenario: Two open plans create the same module
- **WHEN** open item #3308's `tasks.md` marks `src/devops_cli/roadmap/stage_constants.py` with `(new)`, and the reply of the item lists the same path in `creates`
- **THEN** the check returns a problem that names the path and #3308

### Requirement: A closed plan is no dependency
The stage job SHALL ignore the plan of a closed item when it finds a dependency or an overlapping create path. The stage job SHALL ignore the plan of an archived change in the same way.

#### Scenario: A closed item's plan names the same path
- **WHEN** a closed item's active change folder on the default branch lists the cited path as `(new)`
- **THEN** the stage job records no dependency on that item, and the check accepts a reply that lists the path in `creates`

#### Scenario: An archived change names the path
- **WHEN** the change folder of an open item is archived on the default branch, and it lists the cited path as `(new)`
- **THEN** the stage job records no dependency on that item, and the check accepts a reply that lists the path in `creates`

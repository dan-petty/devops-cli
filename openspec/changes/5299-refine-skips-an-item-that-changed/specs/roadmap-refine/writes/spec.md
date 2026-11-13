## ADDED Requirements

### Requirement: A refine round skips an item that changed since the read
A refine round in the Service SHALL NOT write the body, the marks or the Status of an item that a person or another job changed between the read and the write, and SHALL NOT fail for it. The next round SHALL read the item again. The change is a write that the store refuses with `RoadmapItemChangedError`, or a body outside the refine section that changed.

#### Scenario: The Status of an item changes during the round
- **WHEN** a person moves item 2 of 3 to Blocked while the model works on it
- **THEN** items 1 and 3 are written, item 2 gets no write and one INFO line, the round ends with `taken=3`, `written=2` and `failed=0` and raises no error, and the next round takes item 2 again

#### Scenario: Another write failure
- **WHEN** the write of item 2 fails with another `GitHubOperationError`
- **THEN** the round raises `RoadmapRefineError` that names item 2

### Requirement: A skipped item writes no result line
A refine round SHALL write no `roadmap job result` line for an item that changed since the read, as an alternatives check whose body changed writes none, and SHALL NOT count the item as written or as failed.

#### Scenario: The store refuses the write of a changed item
- **WHEN** the store refuses the write of item 2 with `RoadmapItemChangedError`
- **THEN** the round logs no result line for item 2

#### Scenario: The body of an item changes during the round
- **WHEN** a person edits the body of item 2 while the model works on it
- **THEN** item 2 stays New, the round logs no result line for item 2, and the round ends with `written=2`

#### Scenario: A write that fails for another reason
- **WHEN** the write of item 2 fails with another `GitHubOperationError`
- **THEN** the result line of item 2 holds `result=error` and `success=false`

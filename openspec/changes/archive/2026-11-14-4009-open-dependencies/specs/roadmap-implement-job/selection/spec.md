## ADDED Requirements

### Requirement: The implement judge leaves out an open dependency
The implement judge SHALL leave out an item when the Dependencies section of its body or of its plan proposal names an open issue, and the reason SHALL name each open issue.

#### Scenario: An open dependency in the issue body
- **WHEN** the issue body names dependency `#123` and issue #123 is open
- **THEN** the judge leaves the item out with a reason that names `#123` and selects no target

#### Scenario: An open dependency in the plan proposal
- **WHEN** the plan proposal lists `#456: the prerequisite` and issue #456 is open
- **THEN** the judge leaves the item out with a reason that names `#456` and selects no target

#### Scenario: A closed dependency
- **WHEN** every dependency of the body and of the plan is closed
- **THEN** the judge selects the item

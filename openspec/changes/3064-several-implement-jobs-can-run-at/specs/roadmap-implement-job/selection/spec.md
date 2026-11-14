## ADDED Requirements

### Requirement: The round takes only items whose change files are disjoint
The implement round SHALL take two or more items of one repository in one round only when the `Changes:` paths of their change folders share no path and hold no parent-child path pair. It MUST take only one of two items whose change sets share a path or hold a parent-child path pair, and MUST leave the other item for a later round.

#### Scenario: Two disjoint items
- **WHEN** two eligible items of one repository have change folders whose `Changes:` lines name no common path and no parent-child path pair, and the limit is 2
- **THEN** the round returns two Jobs for that round

#### Scenario: Two overlapping items
- **WHEN** two eligible items of one repository share one changed path and the limit is 2
- **THEN** the round returns one Job and leaves the other item for a later round

### Requirement: An item with no change set runs alone
The round MUST select an item alone when the plan of that item names no change file or when the round cannot read the change file set of that plan, and MUST select no other item with it.

#### Scenario: An empty change set
- **WHEN** the plan of an item that the round selects names no change file
- **THEN** the round creates one Job and no other Job in that round

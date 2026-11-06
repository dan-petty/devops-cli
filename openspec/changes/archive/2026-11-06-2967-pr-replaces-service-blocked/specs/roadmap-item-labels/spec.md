## MODIFIED Requirements

### Requirement: A Status moves forward only
In Progress SHALL replace no Status but New, Ready, Planned or none. In Review SHALL replace those and In Progress. Both SHALL also replace a Blocked Status that a job recorded with a stop on record (`implement.stopped`). A Blocked Status that a person set by hand SHALL stay.

#### Scenario: An item that is Blocked or already In Review
- **WHEN** `devops pr create` runs for a pull request that closes an item that a person set Blocked, or an item that is In Review
- **THEN** the Status of the item does not change

#### Scenario: An item that is Planned
- **WHEN** `devops pr create` runs for a pull request that closes a Planned item
- **THEN** the Status of the item is In Progress

#### Scenario: An item that a stop of a job set Blocked, then pr create
- **WHEN** `devops pr create` runs for a pull request that closes an item that is Blocked, whose recorded Status is Blocked and whose record holds `implement.stopped`
- **THEN** the Status of the item is In Progress

#### Scenario: An item that a stop of a job set Blocked, then pr ready
- **WHEN** `devops pr ready` runs for a pull request that closes an item that is Blocked, whose recorded Status is Blocked and whose record holds `implement.stopped`
- **THEN** the Status of the item is In Review

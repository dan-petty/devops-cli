# Spec Delta

## MODIFIED Requirements

### Requirement: A Status moves forward only
In Progress SHALL replace no Status but New, Ready, Planned or none. In Review SHALL replace those and In Progress. A Blocked item SHALL stay Blocked.

#### Scenario: An item that is Blocked or already In Review
- **WHEN** `devops pr create` runs for a pull request that closes a Blocked item, or an item that is In Review
- **THEN** the Status of the item does not change

#### Scenario: An item that is Planned
- **WHEN** `devops pr create` runs for a pull request that closes a Planned item
- **THEN** the Status of the item is In Progress

## ADDED Requirements

### Requirement: The Status family has six labels
The Status family SHALL hold `status/new`, `status/ready`, `status/planned`, `status/in-progress`, `status/in-review` and `status/blocked`, in this order. `.github/labels.yml` SHALL declare each of them.

#### Scenario: The labels file
- **WHEN** the file `.github/labels.yml` is read
- **THEN** it declares all six `status/*` labels

#### Scenario: A Planned issue
- **WHEN** an issue holds `status/planned`
- **THEN** its Item has the Status `Planned`

### Requirement: The Service sets the Status from the job record
One function SHALL derive the Status of an item: Blocked when it is stopped, else In Progress while a Job holds it, else In Review when its delivery pull request is open and ready, else Planned when its plan is on the default branch, else Ready. The rows `implement`, `stage` and `stage_ready` SHALL write that Status with the family replace of the store. They SHALL write only an open item that holds Ready or Planned.

#### Scenario: A round from staging to a closed issue
- **WHEN** an item is staged, its plan is merged, a Job is made for it, its pull request is ready, and the issue closes
- **THEN** its label is `status/ready`, then `status/planned`, then `status/in-progress`, then `status/in-review`, and then none

#### Scenario: A drift
- **WHEN** an item holds `status/ready` that a job wrote and its plan is on the default branch
- **THEN** the next round of the row `implement` or `stage` replaces the label with `status/planned`

#### Scenario: A plan pull request that merged
- **WHEN** the row `stage_ready` reads the recorded stage pull request of a Ready item and it is merged
- **THEN** the item is Planned

#### Scenario: A stop
- **WHEN** the function gets the fact that the item is stopped
- **THEN** it returns Blocked

#### Scenario: An item in another Status
- **WHEN** an item is New, In Progress, In Review or Blocked
- **THEN** no round changes its label

### Requirement: The Service never reverts a person's Status
The Service SHALL write the Status of an item only when its label equals the Status that a job last recorded for it. A label that a person set, or added next to the recorded one, SHALL stay. A write after a change of a person between the read and the write SHALL raise `RoadmapItemChangedError` and change nothing.

#### Scenario: A person moves the label
- **WHEN** a job recorded Planned for an item and a person then sets `status/ready`, and the plan is on the default branch
- **THEN** the round leaves `status/ready`

#### Scenario: An item with no record
- **WHEN** a person labeled an item `status/ready` and no job ever wrote its Status
- **THEN** the round leaves the label

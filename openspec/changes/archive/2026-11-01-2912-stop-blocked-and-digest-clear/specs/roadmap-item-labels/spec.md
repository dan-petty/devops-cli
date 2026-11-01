# Spec Delta

## MODIFIED Requirements

### Requirement: The Service sets the Status from the job record
One function SHALL derive the Status of an item: In Progress while a Job holds it, else Blocked while the record holds `implement.stopped`, else Planned when its plan is on the default branch, else Ready. The rows `implement`, `stage` and `stage_ready` SHALL write it by family replace, only for an open item that holds Ready or Planned. The runner Job and `devops pr ready` SHALL set In Review. The stop path SHALL set Blocked, and only a clear rule of the row `implement` SHALL end it.

#### Scenario: A round from staging to a closed issue
- **WHEN** an item is staged, its plan is merged, a Job is made for it, the Job marks its pull request ready, and the issue closes
- **THEN** its label is `status/ready`, then `status/planned`, then `status/in-progress`, then `status/in-review` (set by the Job), and then none

#### Scenario: A drift
- **WHEN** an item holds `status/ready` that a job wrote and its plan is on the default branch
- **THEN** the next round of the row `implement` or `stage` replaces the label with `status/planned`

#### Scenario: A plan pull request that merged
- **WHEN** the row `stage_ready` reads the recorded stage pull request of a Ready item and it is merged
- **THEN** the item is Planned

#### Scenario: A stop on a Ready item
- **WHEN** an item holds `status/ready` that a job wrote and its record holds `implement.stopped`
- **THEN** the next sweep replaces the label with `status/blocked`

#### Scenario: An item in another Status
- **WHEN** an item is New, In Progress, In Review or Blocked
- **THEN** no sweep changes its label

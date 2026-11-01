# Spec Delta

## MODIFIED Requirements

### Requirement: A claim of a person or an agent ends the Job at the next group boundary
The implement job SHALL read the Item before each unticked task group, when a step stops, and before the push. When the Item holds `owner/agent` or `owner/human`, the job SHALL end the Item at once: it SHALL push nothing, open no pull request, comment the owner and the boundary, and change neither the Status nor the owner. The round that reports the Job SHALL NOT set such an Item Blocked and SHALL NOT record `implement.stopped`.

#### Scenario: A person claims while group 1 runs
- **WHEN** the Item holds `owner/human` when group 1 ends, and the change has a group 2
- **THEN** the job runs no step for group 2, pushes nothing, opens no pull request, and comments that a person claimed the Item

#### Scenario: A claim before the first group
- **WHEN** the Item holds `owner/agent` when the job starts its first group
- **THEN** the job runs no step and pushes nothing

#### Scenario: A claim after the last group
- **WHEN** the Item holds `owner/human` after the last group passed, or after the docs and the archive steps
- **THEN** the job does not push, does not mark a pull request ready, and opens no pull request

#### Scenario: A claim while a group runs and fails
- **WHEN** the Item holds `owner/human` when a group stops the job
- **THEN** the job pushes nothing, opens no pull request, sets no Status, records no `implement.stopped`, and comments that a person claimed the Item

#### Scenario: The Service holds the Item
- **WHEN** the Item holds `owner/service` for the whole run
- **THEN** the job runs every group and ends as before

#### Scenario: The round reports the Job
- **WHEN** a round reports the Job that ended this way, and the Item is In Progress with `owner/human`
- **THEN** the Item stays In Progress, holds no `implement.stopped` record, and the Job state is recorded

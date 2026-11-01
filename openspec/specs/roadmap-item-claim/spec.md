# roadmap-item-claim Specification

## Purpose
How an agent, a person and the Service claim a roadmap Item with one `owner/*` label, how a claim is released, and how a claim by a person ends the Job of the Service without a pull request over the work.

## Requirements

### Requirement: A claim sets the owner label of one owner
`devops roadmap claim <issue> --as agent|human` SHALL set the label `owner/agent` or `owner/human` on the Item and SHALL remove every other `owner/*` label. A claim by the owner that already holds the Item SHALL change nothing. A claim of an Item that the Service holds SHALL succeed when the claim is `human` and SHALL be refused when it is `agent`. A claim of an Item that another owner holds SHALL be refused with `RoadmapClaimError` that names the owner, and SHALL change nothing.

#### Scenario: A free Item
- **WHEN** an agent claims an Item that holds no `owner/*` label
- **THEN** the Item holds `owner/agent` and no other `owner/*` label

#### Scenario: A person takes an Item from the Service
- **WHEN** a person claims an Item that holds `owner/service`
- **THEN** the Item holds `owner/human` and not `owner/service`

#### Scenario: A second owner
- **WHEN** an agent claims an Item that holds `owner/human`, or a person claims an Item that holds `owner/agent`, or an agent claims an Item that holds `owner/service`
- **THEN** the command exits 1, the message names the owner that holds the Item, and the labels do not change

#### Scenario: The same owner twice
- **WHEN** an agent claims an Item that holds `owner/agent`
- **THEN** no write is sent and the command exits 0

#### Scenario: A candidate
- **WHEN** a claim names an issue that holds no `priority/*` label
- **THEN** the command exits 1 and names the issue as no Item of the roadmap

#### Scenario: A closed issue
- **WHEN** a claim names a closed issue
- **THEN** the command exits 1 and says that the issue is closed, and a release of a closed issue clears its `owner/*` label

### Requirement: A release clears the owner label
`devops roadmap release <issue>` SHALL remove every `owner/*` label of the Item. A release of an Item with no owner SHALL send no write.

#### Scenario: A held Item
- **WHEN** a person releases an Item that holds `owner/agent`
- **THEN** the Item holds no `owner/*` label

#### Scenario: A free Item
- **WHEN** a person releases an Item that holds no `owner/*` label
- **THEN** no write is sent and the command exits 0

### Requirement: The claim commands write only with confirm
Without `--confirm`, `claim` and `release` SHALL print the plan and change nothing. With `--dry-run`, they SHALL make no request and SHALL list the requests of a run.

#### Scenario: No confirm
- **WHEN** `claim 7 --as agent` runs without `--confirm`
- **THEN** the output says that nothing was written and the Item is unchanged

#### Scenario: A dry run
- **WHEN** `claim 7 --as agent --dry-run` runs
- **THEN** the store records no write and the output lists the issue read and the label write

### Requirement: The Service claims an Item for the Job it creates
The `implement` row of the Service SHALL set `owner/service` in the write that records the Job on the Item, and SHALL remove it in the write that records the state of the ended Job. When the creation of the Job fails, it SHALL remove the label with the record. It SHALL create no Job for an Item that another owner holds when the round writes the claim, and that round SHALL not fail. It SHALL remove no label of another owner.

#### Scenario: A Job is created
- **WHEN** the round creates a Job for an Item that holds no owner
- **THEN** the Item holds `owner/service` and its record names the Job

#### Scenario: The Job ends
- **WHEN** a later round reports that the Job of an Item that holds `owner/service` ended
- **THEN** the Item holds no `owner/*` label and its record holds the state of the Job

#### Scenario: The creation fails
- **WHEN** the Kubernetes API refuses the creation of the Job
- **THEN** the Item holds no `owner/*` label, its record names no Job, and the round raises the error

#### Scenario: A person claims before the Job exists
- **WHEN** a person claims the planned Item after the plan and before the write of the round
- **THEN** no Job is created, the Item keeps `owner/human`, the round does not fail, and the round logs that it left the Item

#### Scenario: A person holds the Item when the Job is reported
- **WHEN** the round reports a Job that ended and the Item holds `owner/human`
- **THEN** the Item keeps `owner/human`

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

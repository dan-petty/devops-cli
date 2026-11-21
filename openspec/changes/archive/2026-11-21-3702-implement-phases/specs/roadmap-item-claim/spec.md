## ADDED Requirements

### Requirement: A claim of a person or an agent ends the Job before its push
The implement job SHALL read the Item in `prepare` before it clones, at the start of `publish`, and in `publish` right before the push (#3702). When the Item holds `owner/agent` or `owner/human`, the job SHALL end the Item at once: it SHALL push nothing, open no pull request, comment the owner and the boundary, and change neither the Status nor the owner. The round that reports the Job SHALL NOT set such an Item Blocked or record `implement.stopped`.

#### Scenario: A claim before the run
- **WHEN** the Item holds `owner/agent` when `prepare` starts
- **THEN** the job runs no step, pushes nothing and comments that an agent claimed the Item

#### Scenario: A person claims while the agent runs
- **WHEN** the Item holds `owner/human` when `publish` starts
- **THEN** the job pushes nothing, opens no pull request, sets no Status, and comments that a person claimed the Item

#### Scenario: A claim while a group runs and fails
- **WHEN** the Item holds `owner/human` when `publish` gets the stop of a group
- **THEN** the job pushes nothing at the stop, opens no pull request, sets no Status, records no `implement.stopped`, and comments that a person claimed the Item

#### Scenario: A claim right before the push
- **WHEN** a person claims the Item after `publish` starts and before its push
- **THEN** the claim check before the push ends the run, and `origin` holds no new commit

#### Scenario: The Service holds the Item
- **WHEN** the Item holds `owner/service` for the whole run
- **THEN** the job runs every group and ends as before

## REMOVED Requirements

### Requirement: A claim of a person or an agent ends the Job at the next group boundary
**Reason**: The agent phase reads no item, so `prepare` and `publish` check the claim (#3702).
**Migration**: The requirement "A claim of a person or an agent ends the Job before its push" replaces it.

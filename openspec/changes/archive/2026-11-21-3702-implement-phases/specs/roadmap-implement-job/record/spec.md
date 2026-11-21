## MODIFIED Requirements

### Requirement: The job record
The job SHALL keep `implement.group` (the last group that passed), `implement.sha` (the commit it ended on), `implement.branch`, `implement.pr`, `implement.checked_sha`, `implement.published_sha`, `implement.stopped`, `implement.result`, `implement.spend` and `implement.trace` in the job record of the item. The spend SHALL count every step of every Job of the item. `publish` SHALL write the record when the run ends (#3702).

#### Scenario: Spend
- **WHEN** two steps used 3 and 4 requests
- **THEN** the record of the spend holds 7 requests

#### Scenario: The branch
- **WHEN** the job takes a Staged item and a Planned item to a draft pull request
- **THEN** the record of each holds its branch and its pull request

#### Scenario: The trace
- **WHEN** the job takes an item to a draft pull request
- **THEN** the record holds `implement.trace` with the events of the steps, the scoped checks and the commands of the job

#### Scenario: A record of an older version
- **WHEN** the record of an item holds no `implement.result`
- **THEN** the record loads with the key absent and every other key unchanged

## REMOVED Requirements

### Requirement: The job record keeps the base until the run ends
**Reason**: Only the withdraw of the checkpoints read `implement.base`, and no run pushes before `publish` (#3702).
**Migration**: None. A record that holds the key keeps it until the next write of the review or of a return.

## ADDED Requirements

### Requirement: A record is the record of the issue that it was written for
The store SHALL read the record block of an issue as an empty job record when the block was written for another issue: a branch that it names in `stage.branch`, in `implement.branch` or in the intent mark `stage.pending` names another issue number than the number of the issue. A branch that names no issue number SHALL tell nothing, and so SHALL a block that names no branch.

#### Scenario: A branch names another issue number
- **WHEN** the body of issue 7 holds a block with `stage.branch` `feat/4107-add-the-rows`, `stage.pr`, `refine.blocked_by` and a Status
- **THEN** the job record of item 7 is empty

#### Scenario: The branch names the issue
- **WHEN** the body of issue 7 holds a block with `stage.branch` `feat/7-add-the-rows`, `stage.pr` and a Status
- **THEN** the job record of item 7 holds each value

#### Scenario: The block names no branch
- **WHEN** the body of issue 7 holds a block with `stage.pr`, a Status and `refine.body_hash`, and no branch
- **THEN** the job record of item 7 holds each value

#### Scenario: A branch that names no issue number
- **WHEN** the body of issue 7 holds a block with `stage.branch` `main` and `refine.body_hash`
- **THEN** the job record of item 7 holds both values

### Requirement: Each reader gives an empty record for the block of another issue
The GitHub store, in the read of one issue and in the listing of every issue, and the reader of an issue event of the Service SHALL read a block by the rule of the record of an issue. The Item and the issue of a read SHALL say whether the body holds a block that was written for another issue (`foreign_record`).

#### Scenario: A block whose branch names another issue number
- **WHEN** the body of issue 7 holds a block with `stage.branch` `feat/4107-add-the-rows`
- **THEN** the read of the issue, the listing and the reader of an issue event each give an empty job record, and each says that the body holds the record of another issue

#### Scenario: A block whose branch names the issue
- **WHEN** the body of issue 7 holds a block with `stage.branch` `feat/7-add-the-rows`, `stage.pr` and a Status
- **THEN** each reader gives each value, and none says that the body holds the record of another issue

### Requirement: One record write replaces a record of another issue
A record write to an issue whose block was written for another issue SHALL merge into no key of that block. The block after the write SHALL hold the keys of the write, and no other key. A write with no mark SHALL leave the body with no block. A record write to the record of the issue SHALL keep each key of the block and SHALL add no key that the write does not name.

#### Scenario: A mark write
- **WHEN** the body of issue 7 holds the block of another issue with `stage.branch` `feat/4107-add-the-rows`, `stage.pr`, `implement.job`, a Status and a key of another version, and a job sets `refine.body_hash`
- **THEN** the block of the body holds `refine.body_hash`, and no other key

#### Scenario: A write with no mark
- **WHEN** the body of issue 7 holds the block of another issue, and a job sends a record write with no mark
- **THEN** the store sends one `PATCH`, and the body holds its text and no block

#### Scenario: A field write
- **WHEN** the body of issue 7 holds the block of another issue with `stage.branch` `feat/4107-add-the-rows` and a Status, and a job sets the Status to Ready
- **THEN** the block of the body holds the Status Ready, and no other key

#### Scenario: A mark write to the record of the issue
- **WHEN** the body of issue 7 holds a block with a Status, `stage.branch` `feat/7-add-the-rows`, `stage.pr` and a key of another version, and a job sets `stage.ready`
- **THEN** the block of the body holds each of these keys with its value and `stage.ready`, and no other key

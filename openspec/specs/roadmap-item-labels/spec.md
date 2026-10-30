# roadmap-item-labels Specification

## Purpose
How the roadmap jobs read and write an Item's Status, Priority, Value and Effort as issue labels and its job record as a hidden block of the issue body, with no request to a project board, and how a job sees a change that a person made.

## Requirements

### Requirement: One label family holds each field of an Item
The roadmap store SHALL read an Item's Status, Priority, Value and Effort each from one label family: the label is the field's name and the value in lower case, with a hyphen for each space, such as `status/in-progress` for the Status `In Progress`. A field SHALL have no value when the issue holds no label of its family.

#### Scenario: An issue with a label of each family
- **WHEN** an issue holds `priority/p1-high`, `status/in-progress`, `value/high` and `effort/low`
- **THEN** its Item has Priority `P1-High`, Status `In Progress`, Value `High` and Effort `Low`

#### Scenario: A label that a person sets
- **WHEN** a person adds `status/blocked` to an Item whose Status a job set to `New`, and leaves `status/new` on it
- **THEN** the next read gives the Item the Status `Blocked`

### Requirement: An Item is an issue with a priority label
The roadmap store SHALL list as Items the issues of the repository, open and closed and never pull requests, that hold a `priority/*` label of the family. It SHALL list as Candidates the open issues that hold none.

#### Scenario: Items and Candidates
- **WHEN** the repository holds an open issue with `priority/p2-medium`, a closed issue with `priority/p3-low`, an open issue with no `priority/*` label and a pull request with `priority/p1-high`
- **THEN** the Items are the two issues with a priority label, and the one Candidate is the open issue without one

### Requirement: A job sets a field by replacing the family's labels
A job's write of a field SHALL remove every label of the field's family from the issue, SHALL add the label of the value, and SHALL write the issue's labels and its job record in one request. A value that is not one of the field's values SHALL raise before any write.

#### Scenario: A job sets the Status
- **WHEN** a job sets the Status of an Item that holds `status/new` and `type/bug` to `Ready`
- **THEN** the issue holds `status/ready` and `type/bug`, its job record names `Ready` for Status, and one write request was sent

#### Scenario: A value that is not a Status
- **WHEN** a job sets the Status of an Item to `Done`
- **THEN** the write raises and the issue is unchanged

### Requirement: A job never reverts a person's change
Before a job writes a field, the store SHALL read the issue. When the field's value there differs from the value that the store read, and from the value that the job writes, the write SHALL raise `RoadmapItemChangedError` and SHALL change nothing.

#### Scenario: A person changed the Status after the read
- **WHEN** a job read an Item with Status `New`, a person then set `status/blocked`, and the job sets the Status to `Ready`
- **THEN** the write raises `RoadmapItemChangedError`, and the issue holds `status/blocked`

### Requirement: The issue body holds the job record
The store SHALL keep an Item's job record in a block `<!-- devops-roadmap-record {...} -->` at the end of the issue body. The body that the store returns SHALL hold no such block, and a body write SHALL keep the issue's block. A block that is not a JSON object SHALL read as an empty record.

#### Scenario: A body write keeps the record
- **WHEN** refine writes a new body to an Item whose job record holds a mark
- **THEN** the body that the store returns is the new body, and the job record still holds the mark

#### Scenario: A person breaks the block
- **WHEN** the record block of an issue holds text that is not JSON
- **THEN** the store reads the issue with an empty job record

### Requirement: Only the comment at the end of the body is the record block
The store SHALL read as the job record block only a comment that is the last block of the issue body. A quote of the block in a code span or a code block, and a comment that more text follows, SHALL stay in the body, SHALL read as no record and SHALL log no warning.

#### Scenario: A body quotes the record format
- **WHEN** the body of an issue quotes the record block in a code span, a fenced code block or an indented code block, or holds the comment before more text
- **THEN** the store returns the body with the quote, reads an empty job record, logs no warning, and the next write of the record keeps the quote

### Requirement: No roadmap job reads or writes a project board
Intake, refine, return, run and the project metrics SHALL send no request to GitHub Projects, and SHALL read no `.github/roadmap.toml`.

#### Scenario: Intake places a candidate
- **WHEN** intake places a candidate against the GitHub fake at the process edge
- **THEN** no request that the fake records names a project, `projectV2` or `.github/roadmap.toml`

### Requirement: The Status follows the pull request that delivers the item
`devops pr create` SHALL set the Status of the open item that the new pull request closes to In Progress, and `devops pr ready` SHALL set it to In Review. A pull request that closes no open item of its repository SHALL change nothing.

#### Scenario: A draft that closes a Ready item
- **WHEN** a person runs `devops pr create` for a pull request that closes the Ready item 7
- **THEN** item 7 has the Status In Progress

#### Scenario: A ready pull request of an In Progress item
- **WHEN** a person runs `devops pr ready` for a pull request that closes the In Progress item 7
- **THEN** item 7 has the Status In Review

#### Scenario: A pull request that closes no item
- **WHEN** `devops pr create` runs for a pull request that closes no issue
- **THEN** no label changes

### Requirement: A Status moves forward only
In Progress SHALL replace no Status but New, Ready or none. In Review SHALL replace those and In Progress. A Blocked item SHALL stay Blocked.

#### Scenario: An item that is Blocked or already In Review
- **WHEN** `devops pr create` runs for a pull request that closes a Blocked item, or an item that is In Review
- **THEN** the Status of the item does not change

### Requirement: A failed Status write is reported
When the closing issues cannot be read or the Status cannot be written, the command SHALL exit 1 and name the pull request and the reason.

#### Scenario: The closing issues cannot be read
- **WHEN** the read of the closing issues fails with "HTTP 502"
- **THEN** the command exits 1 and its message names the reason

### Requirement: A closed issue holds no Status label
The workflow `.github/workflows/clear-status.yml` SHALL remove every `status/*` label of an issue when the issue closes, and SHALL remove no other label.

#### Scenario: A merge closes an issue
- **WHEN** an issue that holds `status/in-review` and `type/bug` closes
- **THEN** the workflow removes `status/in-review` and keeps `type/bug`

### Requirement: Two writers of one issue keep each other's keys of the job record
Each write of the job record of an issue (a field write with its marks, a mark write and a body write) SHALL read the issue, and SHALL send its `PATCH`, before another write of the process reads that issue. A write SHALL change only the keys it names and keep every other key of the record that the issue holds at its read. This holds for stores that different lanes of the Service opened.

#### Scenario: A field write with refine marks and a mark write of the implement row
- **WHEN** one store sets the Status of an Item with the mark `refine.body_hash`, and while it holds its read, a second store sets `implement.job` on the same Item
- **THEN** the record of the Item holds both keys, and the Status

#### Scenario: A body write and a mark write
- **WHEN** one store writes a new body to an issue, and while it holds its read, a second store sets `implement.job`
- **THEN** the issue holds the new body, and its record holds `implement.job`

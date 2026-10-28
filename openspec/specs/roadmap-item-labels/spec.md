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

### Requirement: No roadmap job reads or writes a project board
Intake, refine, return, run and the project metrics SHALL send no request to GitHub Projects, and SHALL read no `.github/roadmap.toml`.

#### Scenario: Intake places a candidate
- **WHEN** intake places a candidate against the GitHub fake at the process edge
- **THEN** no request that the fake records names a project, `projectV2` or `.github/roadmap.toml`

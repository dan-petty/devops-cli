# Spec Delta

## ADDED Requirements

### Requirement: Two writers of one issue keep each other's keys of the job record
Each write of the job record of an issue (a field write with its marks, a mark write and a body write) SHALL read the issue, and SHALL send its `PATCH`, before another write of the process reads that issue. A write SHALL change only the keys it names and keep every other key of the record that the issue holds at its read. This holds for stores that different lanes of the Service opened.

#### Scenario: A field write with refine marks and a mark write of the implement row
- **WHEN** one store sets the Status of an Item with the mark `refine.body_hash`, and while it holds its read, a second store sets `implement.job` on the same Item
- **THEN** the record of the Item holds both keys, and the Status

#### Scenario: A body write and a mark write
- **WHEN** one store writes a new body to an issue, and while it holds its read, a second store sets `implement.job`
- **THEN** the issue holds the new body, and its record holds `implement.job`

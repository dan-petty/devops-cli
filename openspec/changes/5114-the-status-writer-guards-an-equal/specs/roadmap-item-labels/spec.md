## MODIFIED Requirements

### Requirement: Every job writes the Status through one writer
Every job and command that sets the Status of an item SHALL write it through `write_status` of `src/devops_cli/roadmap/status_sync.py`. The writer SHALL derive the Status from the facts of its caller, SHALL write the label only when it differs, and SHALL read the issue again after the write. When the label is equal, it SHALL write only the marks and the body of its caller. When someone changed the Status since its caller read the item, the writer SHALL raise `RoadmapItemChangedError` and SHALL write nothing, also when the label is equal. A dry run SHALL send no request and SHALL return the would-be write.

#### Scenario: An equal label
- **WHEN** the writer gets facts whose Status is the label of the item
- **THEN** it sends no label write and no read

#### Scenario: A changed label
- **WHEN** the facts give another Status than the label of the item
- **THEN** the writer sends one label write and one read of the issue, and the label is the derived Status

#### Scenario: An equal label that someone changed since the read
- **WHEN** a caller read the item as Ready, a person then set `status/new`, and the caller writes Ready with marks and a body
- **THEN** the writer raises `RoadmapItemChangedError`, the issue holds `status/new`, and its marks and body are as they were

#### Scenario: A dry run
- **WHEN** the writer runs as a dry run
- **THEN** it sends no request, and it returns the label of the item and the derived Status

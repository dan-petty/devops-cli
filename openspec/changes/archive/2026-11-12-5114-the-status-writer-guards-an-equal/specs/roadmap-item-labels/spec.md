## ADDED Requirements

### Requirement: The Status writer guards an equal label
When the label of the item that its caller read equals the derived Status, and someone changed the Status since that read, `write_status` SHALL raise `RoadmapItemChangedError` and SHALL write no mark and no body (ADR 0002).

#### Scenario: An equal label that someone changed since the read
- **WHEN** a caller read the item as Ready, a person then set `status/new`, and the caller writes Ready with marks and a body
- **THEN** the writer raises `RoadmapItemChangedError`, the issue holds `status/new`, and its marks and body are as they were

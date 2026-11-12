## MODIFIED Requirements

### Requirement: The Service reads through the snapshot
The intake rounds of the triage lane and the scoped intake of each delivery SHALL read every issue through the snapshot that the Service keeps in `listing` of its state directory. The status lane SHALL read every issue through its own snapshot in `listing-status` of the state directory. The model lane SHALL read the whole listing.

#### Scenario: A scoped intake with a kept snapshot
- **WHEN** The Service keeps a snapshot of 250 items, and a delivery says that issue 251 opened
- **THEN** The scoped intake sends one listing request, with `since=<watermark>`, and places issue 251

#### Scenario: The store of each lane
- **WHEN** The status, triage and model lanes each open their store for a poll
- **THEN** The store of the status lane reads through the snapshot in `listing-status`, the store of the triage lane through the snapshot in `listing`, and the store of the model lane reads the whole listing

#### Scenario: A status round with a kept snapshot
- **WHEN** The status lane ran one round, and a second round is due
- **THEN** The second round sends one listing request, with `since=<watermark>`

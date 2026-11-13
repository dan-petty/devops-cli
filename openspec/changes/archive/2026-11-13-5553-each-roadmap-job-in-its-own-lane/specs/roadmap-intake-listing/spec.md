## MODIFIED Requirements

### Requirement: The Service reads through the snapshot
The rounds of the lane that holds `intake` and the scoped intake of each delivery SHALL read every issue through the snapshot that the Service keeps in `listing` of its state directory. Each other lane SHALL read every issue through its own snapshot in `listing-<lane>` of the state directory.

#### Scenario: A scoped intake with a kept snapshot
- **WHEN** The Service keeps a snapshot of 250 items, and a delivery says that issue 251 opened
- **THEN** The scoped intake sends one listing request, with `since=<watermark>`, and places issue 251

#### Scenario: The store of each lane
- **WHEN** The lanes `metrics`, `intake` and `refine` each open their store for a poll
- **THEN** The store of `metrics` reads through the snapshot in `listing-metrics`, the store of `intake` through the snapshot in `listing`, and the store of `refine` through the snapshot in `listing-refine`

#### Scenario: A status round with a kept snapshot
- **WHEN** The lane `stage_ready` ran one round, and a second round is due
- **THEN** The second round sends one listing request, with `since=<watermark>`

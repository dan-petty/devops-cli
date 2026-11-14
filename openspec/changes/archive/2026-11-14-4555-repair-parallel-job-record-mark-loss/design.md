# Design

## Decisions

### 1. Unified Write and Repair Helper
`GitHubRoadmapStore` uses a private helper `_patch_and_verify` for `set_field`, `set_marks`, and `write_issue_body`. This helper encapsulates the `PATCH`, read-back comparison, and retry loop so that all record mutations share identical safeguards.

### 2. Up to Two Rewrites
The store attempts at most two rewrites (three writes total). If a mark remains missing after the second rewrite, the operation fails and raises `RoadmapRecordMarkLostError`.

### 3. Comparing Writer Marks Only
The read-back verification checks only the marks that the current writer explicitly set in its changes dictionary. New marks added by other concurrent writers are valid additions and do not trigger a repair.

### 4. Preserving and Restoring Human Edits
When the text outside the record block differs between the pre-write read and the post-write state, the store preserves the external edit, reapplies the record, and increments `devops_cli_roadmap_record_lost_edit_total`.

### 5. Telemetry and Logging
- Each repair emits `devops_cli_roadmap_record_repairs_total` with labels `method` and `mark`.
- Each restored person edit emits `devops_cli_roadmap_record_lost_edit_total`.
- The store logs a warning for each repair and each restored edit.

## Rejected alternatives

### Rely solely on process locks
`_JOB_RECORD_LOCK` operates only within a single Python process. It cannot coordinate with the runner Job pod, claim commands, or future out-of-process workers.

### Unbounded retry loop
An unbounded loop could enter an infinite cycle if a mark cannot be persisted or if GitHub repeatedly drops specific keys.

### Compare entire record
Comparing the full record dictionary would falsely flag normal parallel additions from other workers as losses.

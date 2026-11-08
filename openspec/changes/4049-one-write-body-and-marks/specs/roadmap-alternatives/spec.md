## ADDED Requirements

### Requirement: A check writes its block and its marks with one request
With `--confirm`, a check SHALL write the new body with the job's block, and the marks of the job record, with one `PATCH` of the issue, and its comment as a separate request after it. A stop of the Service after the write SHALL leave the block and `alternatives.checked_at` together, so the next round SHALL NOT take the item as one with no check. The dry-run plan SHALL list no separate write of the body.

#### Scenario: A stop after the write of a check
- **WHEN** a check writes the block and the Service stops right after the write
- **THEN** the body holds the block, the job record holds `alternatives.checked_at`, and the next selection does not take the item

#### Scenario: The requests of one check
- **WHEN** `--confirm` writes one check
- **THEN** the run makes one write of the issue and one comment, and no label changes

#### Scenario: The dry-run plan of a check
- **WHEN** `devops roadmap alternatives --dry-run --item 7` plans the writes
- **THEN** the plan lists one read of issue 7, one `PATCH` for the body with the marks, and the comment

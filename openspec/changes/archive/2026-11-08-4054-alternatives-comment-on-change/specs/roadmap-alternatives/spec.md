## MODIFIED Requirements

### Requirement: A check writes a comment, a block and a record
With `--confirm`, a check SHALL replace the block `devops-roadmap-alternatives:start` to `:end` in the body, or add it at the end, and record `alternatives.checked_at`, `alternatives.body_hash`, `alternatives.verdict` and `alternatives.tool` in the job record. The check SHALL post one comment with the marker `devops roadmap alternatives` when it is the first check of the item, with no recorded `alternatives.verdict`, or when its verdict or its tool differs from the recorded `alternatives.verdict` or `alternatives.tool`. A check with the same verdict and the same tool as the record SHALL post no comment and SHALL still write the block and the record, so `alternatives.checked_at` moves. The check SHALL NOT change a label and SHALL NOT close the issue.

#### Scenario: A marker with no partner
- **WHEN** the body holds the start marker of the block with no end marker, or the end marker with no start marker before it
- **THEN** the item is skipped with a named reason, no comment and no block is written for it, and the person's text is not changed

#### Scenario: Refine ignores the job's writes
- **WHEN** the job has written its block and its comment on an item that refine left waiting on a person
- **THEN** refine hashes the body without the block, takes the comment as no reply, and the item still waits and no model call is made

#### Scenario: A covering tool
- **WHEN** a run with `--confirm` checks an item and the reply names a maintained covering tool whose facts were read
- **THEN** the issue has one comment with the marker, its body has one block with the verdict and the tool, its job record has the four keys, its labels are unchanged and it is open

#### Scenario: A first check
- **WHEN** a check ends for an item whose job record holds no `alternatives.verdict`
- **THEN** the check posts its comment

#### Scenario: A recheck with the same result
- **WHEN** a recheck ends with the verdict and the tool that the job record holds
- **THEN** the check posts no second comment, the block shows the new date, `alternatives.checked_at` holds the new time, and the next selection does not take the item before the recheck days pass

#### Scenario: A recheck with a new verdict or a new tool
- **WHEN** a recheck ends with a verdict that differs from the record, or with a tool that differs from the record, or with a tool where the record holds none
- **THEN** the check posts one comment and records the new verdict, the new tool and the new date

### Requirement: A check writes its block and its marks with one request
With `--confirm`, a check SHALL write the new body with the job's block, and the marks of the job record, with one `PATCH` of the issue, and its comment, when it posts one, as a separate request after it. A stop of the Service after the write SHALL leave the block and `alternatives.checked_at` together, so the next round SHALL NOT take the item as one with no check. The dry-run plan SHALL list no separate write of the body, and SHALL list the comment with the condition that the check is a first one or that its result changed.

#### Scenario: A stop after the write of a check
- **WHEN** a check writes the block and the Service stops right after the write
- **THEN** the body holds the block, the job record holds `alternatives.checked_at`, and the next selection does not take the item

#### Scenario: The requests of one check
- **WHEN** `--confirm` writes one check with a first result or a changed result
- **THEN** the run makes one write of the issue and one comment, and no label changes

#### Scenario: The requests of a recheck with the same result
- **WHEN** `--confirm` writes a recheck with the verdict and the tool of the record
- **THEN** the run makes one write of the issue and no comment, and no label changes

#### Scenario: The dry-run plan of a check
- **WHEN** `devops roadmap alternatives --dry-run --item 7` plans the writes
- **THEN** the plan lists one read of issue 7, one `PATCH` for the body with the marks, and the comment with the condition that the check is a first one or that its verdict or its tool differs from the record

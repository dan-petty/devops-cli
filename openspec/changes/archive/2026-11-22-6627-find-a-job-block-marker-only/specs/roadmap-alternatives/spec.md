## ADDED Requirements

### Requirement: A marker bounds a block only as an HTML block
A check SHALL treat a marker as a block boundary only where CommonMark parses it as an HTML block of its own. A marker on the whole last line of a comment SHALL be a boundary too. A marker that a person quotes in a code span, a code block or a paragraph SHALL stay in the person's text. The check SHALL add its block at the end of a body that holds no such pair. A start marker or an end marker that is a boundary with no partner SHALL stop the write.

#### Scenario: The body quotes both markers
- **WHEN** a body quotes the alternatives start marker and the alternatives end marker in code spans, with the word to between them, and holds no alternatives block
- **THEN** the check writes its block at the end of the body, and the quoted sentence still reads the start marker, to, and the end marker in code spans

#### Scenario: A real block is replaced
- **WHEN** the body holds an alternatives block whose start marker and end marker are each an HTML block on a line of its own
- **THEN** the check replaces that block and keeps every character outside it unchanged

#### Scenario: A person opens a comment above the block
- **WHEN** the body holds an alternatives block, and a person opens an HTML comment above it and does not close it
- **AND** the check runs three times on the item
- **THEN** the start marker ends the comment and bounds the block
- **AND** the first write replaces the block in place
- **AND** after each run the body holds one block, and only the first run checks the item

### Requirement: A check keeps its block readable after an open block
The check SHALL close a code fence or an HTML block that its own text leaves open, before its end marker. When the body ends in an open code fence or HTML block where the check adds its block, the check SHALL close that block on a line of its own before the start marker. The check SHALL record as `alternatives.body_hash` the hash of the body that it writes, so the next run finds one block and reads the item as unchanged.

#### Scenario: The text of a person leaves a code fence open
- **WHEN** the body of a person ends in a code fence that it does not close, and the check runs three times on the item
- **THEN** the first write adds the close of the fence on a line of its own before the block
- **AND** the text of the person stays at the start of the body
- **AND** after each run the body holds one block that a read finds, and only the first run checks the item

#### Scenario: The text of a person leaves a pre block open
- **WHEN** the body of a person ends in a `<pre>` HTML block that it does not close, and the check runs three times on the item
- **THEN** the first write adds `</pre>` on a line of its own before the block, and after each run the body holds one block and only the first run checks the item

#### Scenario: The reason of the model opens a code fence
- **WHEN** the reason in the reply of the model opens a code fence and does not close it, and the check runs three times on the item
- **THEN** after each run the body holds one block that a read finds, and only the first run checks the item

## MODIFIED Requirements

### Requirement: A check writes a comment, a block and a record
With `--confirm`, a check SHALL replace the block `devops-roadmap-alternatives:start` to `:end` in the body, or add it at the end, and record `alternatives.checked_at`, `alternatives.body_hash`, `alternatives.verdict` and `alternatives.tool` in the job record. The block SHALL hold the current result of the check. The comment, when the check posts one, SHALL hold the event of a change of the result. The check SHALL NOT change a label and SHALL NOT close the issue.

#### Scenario: A marker with no partner
- **WHEN** the body holds the start marker of the block as an HTML block on a line of its own with no end marker, or the end marker as an HTML block with no start marker before it
- **THEN** the item is skipped with a named reason, no comment and no block is written for it, and the person's text is not changed

#### Scenario: Refine ignores the job's writes
- **WHEN** the job has written its block and its comment on an item that refine left waiting on a person
- **THEN** refine hashes the body without the block, takes the comment as no reply, and the item still waits and no model call is made

#### Scenario: A covering tool
- **WHEN** a run with `--confirm` checks an item and the reply names a maintained covering tool whose facts were read
- **THEN** the issue has one comment with the marker, its body has one block with the verdict, the tool, the reason, the covers and the lacks, its job record has the four keys, its labels are unchanged and it is open

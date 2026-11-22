## ADDED Requirements

### Requirement: A check replaces its block in a block that a person leaves open
A fenced code block or an HTML block that no close ends runs to the end of the body. The check SHALL read the job blocks at the end of such a block as its end. The check SHALL close the open block on a line of its own before the first of these blocks. The check SHALL replace its block in place. A refine section that the open block holds SHALL stay a section that a read finds. Each other job block marker in the open block SHALL stay the text of the person.

#### Scenario: A person opens a code fence above the block
- **WHEN** the body holds an alternatives block, and a person opens a code fence above it and does not close it
- **AND** the check runs three times on the item
- **THEN** the first write adds the close of the fence on a line of its own before the start marker
- **AND** the first write replaces the block in place
- **AND** after each run the body holds one block, and only the first run checks the item

#### Scenario: A person opens a pre block above the block
- **WHEN** the body holds an alternatives block, and a person opens a `<pre>` block above it and does not close it
- **AND** the check runs three times on the item
- **THEN** the first write adds `</pre>` on a line of its own before the start marker, and after each run the body holds one block

#### Scenario: A refine section comes first in the open block
- **WHEN** a person opens a code fence above a refine section that an alternatives block follows, and does not close it
- **AND** the check runs three times on the item
- **THEN** the first write adds the close of the fence before the refine start marker, and the refine section stays before the block
- **AND** after each run the body holds one block, and only the first run checks the item

#### Scenario: A person quotes a block of the check in an open fence above the block
- **WHEN** a person quotes a block of the check in a code fence above the block of the check
- **AND** the person writes more text in the fence and does not close it
- **AND** the check runs three times on the item
- **THEN** the first write closes the fence before the block of the check and replaces that block in place
- **AND** the quote keeps each of its lines, and only the first run checks the item

#### Scenario: A person quotes one marker in an open fence
- **WHEN** a person quotes the start marker of the check in a code fence that they do not close
- **AND** the body holds no block of the check
- **AND** the check runs three times on the item
- **THEN** the first write closes the fence at the end of the body and adds the block after it
- **AND** the quote keeps each of its lines, and only the first run checks the item

## MODIFIED Requirements

### Requirement: A marker bounds a block only as an HTML block
A check SHALL treat a marker as a block boundary only where CommonMark parses it as an HTML block of its own. A marker on the whole last line of a comment or of a declaration such as `<!DOCTYPE` SHALL be a boundary too. A marker that a person quotes in a code span, a code block or a paragraph SHALL stay in the text of the person. The check SHALL add its block at the end of a body that holds no such pair. A start marker or an end marker that is a boundary with no partner SHALL stop the write.

#### Scenario: The body quotes both markers
- **WHEN** a body quotes the alternatives start marker and the alternatives end marker in code spans, with the word to between them
- **AND** the body holds no alternatives block
- **THEN** the check writes its block at the end of the body
- **AND** the quoted sentence still reads the start marker, to, and the end marker in code spans

#### Scenario: The check replaces a real block
- **WHEN** the body holds an alternatives block whose start marker and end marker are each an HTML block on a line of its own
- **THEN** the check replaces that block and keeps every character outside it unchanged

#### Scenario: A person opens a comment above the block
- **WHEN** the body holds an alternatives block, and a person opens an HTML comment above it and does not close it
- **AND** the check runs three times on the item
- **THEN** the start marker ends the comment and bounds the block
- **AND** the first write replaces the block in place
- **AND** after each run the body holds one block, and only the first run checks the item

#### Scenario: A person opens a declaration above the block
- **WHEN** the body holds an alternatives block, and a person writes `<!DOCTYPE html` above it with no `>`
- **THEN** the start marker ends the declaration and bounds the block

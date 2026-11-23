## MODIFIED Requirements

### Requirement: A marker bounds a block only as an HTML block
A check SHALL treat a marker as a block boundary only where CommonMark parses it as an HTML block of its own. A marker on the last line of a comment or a declaration SHALL be a boundary too. So SHALL a marker line in an HTML block that only a blank line ends. A marker that a person quotes in a code span, a code block or a paragraph SHALL stay their text. The check SHALL add its block at the end of a body that holds no such pair. A boundary marker with no partner SHALL stop the write.

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

#### Scenario: A person removes the blank line above the block
- **WHEN** the body holds an alternatives block, and a person puts a `<details>` part or `<div>x</div>` directly above it
- **AND** the check runs three times on the item
- **THEN** the first write adds a blank line after the text of the person and replaces the block in place
- **AND** after each run the body holds one block, and only the first run checks the item

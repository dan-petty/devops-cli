## ADDED Requirements

### Requirement: A check replaces its block in a block that a person leaves open
A fenced code block or an HTML block that no close ends runs to the end of the body. The check SHALL read the job blocks at the end of such a block as its end. The check SHALL close the open block on a line of its own before the first of these blocks, and SHALL replace its block in place. A refine section that the open block holds SHALL stay a section that a read finds. Each other job block marker in the open block SHALL stay the text of the person.

#### Scenario: A person opens a code fence above the block
- **WHEN** the body holds an alternatives block, and a person opens a code fence above it and does not close it
- **AND** the check runs three times on the item
- **THEN** the first write adds the close of the fence on a line of its own before the start marker, and replaces the block in place
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
- **WHEN** a person quotes a block of the check in a code fence, writes more text in the fence, and does not close it above the block of the check
- **AND** the check runs three times on the item
- **THEN** the first write closes the fence before the block of the check and replaces that block in place
- **AND** the quote keeps each of its lines, and only the first run checks the item

#### Scenario: A person quotes one marker in an open fence
- **WHEN** a person quotes the start marker of the check in a code fence that they do not close, and the body holds no block of the check
- **AND** the check runs three times on the item
- **THEN** the first write closes the fence at the end of the body and adds the block after it
- **AND** the quote keeps each of its lines, and only the first run checks the item

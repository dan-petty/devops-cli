## ADDED Requirements

### Requirement: A check replaces its block in a block that a person leaves open
A fenced code block or an HTML block that no close ends runs to the end of the body. When such a block holds a line that is a job block marker on its own, the check SHALL read that line as the end of the open block. The check SHALL close the open block on a line of its own before that line, and SHALL replace its block in place. A refine section that the open block holds SHALL stay a section that a read finds.

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

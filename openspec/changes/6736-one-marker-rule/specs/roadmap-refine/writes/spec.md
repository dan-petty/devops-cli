## ADDED Requirements

### Requirement: Refine finds its section in a block that a person leaves open
A fenced code block or an HTML block that no close ends runs to the end of the body. When such a block holds a line that is a job block marker on its own, that line SHALL end the open block for a read, so a read finds the section. The outside text of the section SHALL hold the close of the open block on a line of its own before that line. Refine SHALL NOT write a second section. A marker in a block that a close ends SHALL stay the text of the person.

#### Scenario: A person opens a code fence above the section
- **WHEN** refine wrote and recorded a section, and then a person opens a code fence above it and does not close it
- **AND** refine runs three rounds on the item
- **THEN** after each round the body holds one refine start marker, and a read finds the section
- **AND** the body does not change after the first round

#### Scenario: A person opens a pre block above the section
- **WHEN** refine wrote and recorded a section, and then a person opens a `<pre>` block above it and does not close it
- **AND** refine runs three rounds on the item
- **THEN** after each round the body holds one refine start marker, a read finds the section, and the body does not change after the first round

#### Scenario: The outside text holds the close
- **WHEN** `extract_section_and_outside` reads a body that opens a code fence, a `<pre>` block or a `<?` block and does not close it, and after it a refine section and an alternatives block
- **THEN** it returns the refine section
- **AND** the outside text holds the close of the open block on a line of its own before the alternatives block

#### Scenario: A closed code fence quotes a section
- **WHEN** a body quotes the start marker and the end marker of refine in a closed code fence, and holds no section
- **THEN** a read finds no section, and the write keeps the quote and adds the section after it

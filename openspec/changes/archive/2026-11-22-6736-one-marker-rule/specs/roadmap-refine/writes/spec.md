## ADDED Requirements

### Requirement: Refine finds its section in a block that a person leaves open
A fenced code block or an HTML block that no close ends runs to the end of the body. The job blocks at the end of such a block SHALL end it for a read, so a read finds the section. The outside text of the section SHALL hold the close of the open block on a line of its own before their first line. Refine SHALL NOT write a second section. Each other job block marker in the open block SHALL stay the text of the person. A marker in a block that a close ends SHALL also stay the text of the person.

#### Scenario: A person opens a code fence above the section
- **WHEN** refine wrote and recorded a section, and then a person opens a code fence above it and does not close it
- **AND** refine runs three rounds on the item
- **THEN** after each round the body holds one refine start marker, and a read finds the section
- **AND** the body does not change after the first round

#### Scenario: A person opens a pre block above the section
- **WHEN** refine wrote and recorded a section, and then a person opens a `<pre>` block above it and does not close it
- **AND** refine runs three rounds on the item
- **THEN** after each round the body holds one refine start marker, and a read finds the section
- **AND** the body does not change after the first round

#### Scenario: The outside text holds the close
- **WHEN** `extract_section_and_outside` reads a body that opens a code fence, a `<pre>` block or a `<?` block and does not close it
- **AND** a refine section and an alternatives block follow the open block
- **THEN** it returns the refine section
- **AND** the outside text holds the close of the open block on a line of its own before the alternatives block

#### Scenario: A closed code fence quotes a section
- **WHEN** a body quotes the start marker and the end marker of refine in a closed code fence, and holds no section
- **THEN** a read finds no section, and the write keeps the quote and adds the section after it

#### Scenario: A person opens a code fence in the section
- **WHEN** `extract_section_and_outside` reads a body whose section holds a code fence that a person opens and does not close, and an alternatives block after the section
- **THEN** it returns the section with the close of the fence on a line of its own before the end marker
- **AND** a read of the alternatives block finds it

#### Scenario: A person quotes one marker in an open fence
- **WHEN** a body quotes the start marker of refine in a code fence that it does not close
- **AND** the body holds no end marker after it, and holds no section
- **AND** refine runs three rounds on the item
- **THEN** the first round keeps the quote, closes the fence at the end of the body and adds the section after it
- **AND** only the first round sends a request to the model

#### Scenario: A person opens a code fence above the block of another job
- **WHEN** a body holds an alternatives block and no section, and a person opens a code fence above the block and does not close it
- **AND** refine runs three rounds on the item
- **THEN** the first round writes the close of the fence on a line of its own before the start marker of the alternatives block
- **AND** the first round adds the section at the end
- **AND** a read finds the alternatives block after each round, and only the first round sends a request to the model

## MODIFIED Requirements

### Requirement: The hash of the body leaves out the job's block
The hash that refine records as `refine.body_hash` SHALL be the hash of the body that refine writes. The hash SHALL leave out the alternatives block and the refine section, as the check for an unchanged item computes it. The check before a write SHALL compare the hash of the whole body outside the refine section. So refine keeps a block that the job wrote after the read. A marker SHALL bound a block only as an HTML block of its own or as the whole last line of a comment or declaration.

#### Scenario: An item with a block reads as unchanged
- **WHEN** refine refines an item whose body holds the block of the job, and the next round reads the item with no change
- **THEN** the item reads as unchanged and the round does not refine it

#### Scenario: The job writes a block during the round
- **WHEN** the job writes a block between the read and the write of refine
- **THEN** refine does not write the body, and the block stays

#### Scenario: A body that quotes the refine markers
- **WHEN** a body quotes the refine start marker and the refine end marker in code spans with text between them, and holds no refine section
- **THEN** `extract_section_and_outside` returns the body as the outside text and None as the section
- **AND** `without_alternatives` keeps the quoted pair and the text between them
- **AND** a refine write adds its section at the end

#### Scenario: A real block is left out of the hash
- **WHEN** a body holds an alternatives block whose start marker and end marker are each an HTML block on a line of its own
- **THEN** the body hash leaves the block out and keeps the text on either side of it

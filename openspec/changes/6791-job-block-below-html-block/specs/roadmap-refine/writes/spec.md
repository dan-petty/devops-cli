## MODIFIED Requirements

### Requirement: The hash of the body leaves out the job's block
The hash that refine records as `refine.body_hash` SHALL be the hash of the body that refine writes. The hash SHALL leave out the alternatives block and the refine section, as the check for an unchanged item computes it. The check before a write SHALL compare the hash of the whole body outside the refine section. A marker SHALL bound a block only as an HTML block of its own, or on the last line of a comment or declaration. A marker line that starts the job blocks at the end SHALL bound one too.

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

#### Scenario: A marker line below an HTML block that a blank line ends
- **WHEN** a body holds `</details>`, `<div>x</div>` or an `<img>` tag directly above the start marker of the refine section and of the alternatives block
- **THEN** `job_block_bounds` and `extract_section_and_outside` find both blocks
- **AND** the outside text holds a blank line before each start marker

#### Scenario: A person removes the blank line above the section
- **WHEN** refine wrote and recorded a section, and then a person puts a `<details>` part or `<div>x</div>` directly above it
- **AND** refine runs three rounds on the item
- **THEN** after each round the body holds one refine start marker, and a read finds the section
- **AND** the first round writes a blank line after the text of the person
- **AND** only the first round sends a request to the model

#### Scenario: A marker in a block that a close ends
- **WHEN** a body quotes a refine section in a closed fence in a `<details>` part, or in a closed `<pre>` or `<?` block
- **THEN** a read finds no section, and the body does not change

#### Scenario: A marker in an HTML block of a person
- **WHEN** a person writes a lone start marker or a marker pair in a `<details>` or `<div>` block
- **AND** a fence line can follow the marker in the block
- **THEN** a read finds only the refine block at the end of the body, and no write changes the body
- **AND** a job block that a line of the person follows in the same HTML block stays unread

#### Scenario: A person writes a start marker in a details block above the section
- **WHEN** refine wrote and recorded a section
- **AND** a person puts a `<details>` block with a refine start marker and a line of text above the section
- **AND** refine runs three rounds on the item
- **THEN** each round keeps each line of the `<details>` block, and a read finds the section
- **AND** only the first round sends a request to the model

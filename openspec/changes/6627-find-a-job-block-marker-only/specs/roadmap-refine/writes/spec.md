## MODIFIED Requirements

### Requirement: The hash of the body leaves out the job's block
The hash that refine records as `refine.body_hash` SHALL be the hash of the body outside the alternatives job's block and refine's section, as the check for an unchanged item computes it. The check before a write SHALL compare the hash of the whole body outside refine's section, so a block that the job wrote after refine read the body is kept. A block SHALL bound the body only at a marker that CommonMark parses as an HTML block of its own.

#### Scenario: An item with a block reads as unchanged
- **WHEN** refine refines an item whose body holds the job's block, and the next round reads the item with no change
- **THEN** the item reads as unchanged and the round does not refine it

#### Scenario: The job writes a block during the round
- **WHEN** the job writes a block between the read and the write of refine
- **THEN** refine does not write the body, and the block stays

#### Scenario: A body that quotes the refine markers
- **WHEN** a body quotes the refine start marker and the refine end marker in code spans with text between them, and holds no refine section
- **THEN** `extract_section_and_outside` returns the body as the outside text and None as the section, `without_alternatives` keeps the quoted pair and the text between them, and a refine write adds its section at the end

#### Scenario: A real block is left out of the hash
- **WHEN** a body holds an alternatives block whose start marker and end marker are each an HTML block on a line of its own
- **THEN** the body hash leaves the block out and keeps the text on either side of it

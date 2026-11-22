## ADDED Requirements

### Requirement: Refine keeps its section readable after an open block
Refine SHALL close a code fence or an HTML block that the model's text leaves open, before the end marker of its section. When the body outside its section ends in an open code fence or HTML block, refine SHALL close that block on a line of its own before the start marker. After each round, the body SHALL hold one refine section that a read finds, and the next round SHALL read the item as unchanged.

#### Scenario: The model's text leaves a code fence open
- **WHEN** the problem statement of the model opens a code fence and does not close it, and refine runs three rounds on the item with no change by a person
- **THEN** after each round the body holds one refine section that a read finds, the item reads as unchanged, and only the first round sends a request to the model

#### Scenario: The text of a person leaves a code fence open
- **WHEN** the body of a person ends in a code fence that it does not close, and refine runs three rounds on the item
- **THEN** the first write adds the close of the fence on a line of its own before the section, the text of the person stays at the start of the body, and after each round the body holds one refine section and the item reads as unchanged

#### Scenario: The text of a person leaves a pre block open
- **WHEN** the body of a person ends in a `<pre>` HTML block that it does not close, and refine runs three rounds on the item
- **THEN** the first write adds `</pre>` on a line of its own before the section, and after each round the body holds one refine section and the item reads as unchanged

## MODIFIED Requirements

### Requirement: The hash of the body leaves out the job's block
The hash that refine records as `refine.body_hash` SHALL be the hash of the body that refine writes, outside the alternatives job's block and refine's section, as the check for an unchanged item computes it. The check before a write SHALL compare the hash of the whole body outside refine's section, so a block that the job wrote after refine read the body is kept. A block SHALL bound the body only at a marker that CommonMark parses as an HTML block of its own.

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

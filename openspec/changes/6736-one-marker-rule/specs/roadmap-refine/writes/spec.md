## ADDED Requirements

### Requirement: Refine replaces its section in a block that a person leaves open
A fenced code block or an HTML block that no close ends runs to the end of the body. When such a block holds a line that is a job block marker on its own, that line SHALL end the open block for a read. Refine SHALL close the open block on a line of its own before that line, and SHALL replace its section. A marker in a block that a close ends SHALL stay the text of the person.

#### Scenario: A person opens a code fence above the section
- **WHEN** refine wrote and recorded a section, and then a person opens a code fence above it and does not close it
- **AND** refine runs three rounds on the item
- **THEN** the first write adds the close of the fence on a line of its own before the start marker, and removes the old section
- **AND** after each round the body holds one refine start marker, a read finds the section, and the item reads as unchanged
- **AND** only the first round sends a request to the model

#### Scenario: A person opens a pre block above the section
- **WHEN** refine wrote and recorded a section, and then a person opens a `<pre>` block above it and does not close it
- **AND** refine runs three rounds on the item
- **THEN** the first write adds `</pre>` on a line of its own before the start marker, and removes the old section
- **AND** after each round the body holds one refine start marker, and the item reads as unchanged

#### Scenario: A closed code fence quotes a section
- **WHEN** a body quotes the start marker and the end marker of refine in a closed code fence, and holds no section
- **THEN** a read finds no section, and the write keeps the quote and adds the section after it

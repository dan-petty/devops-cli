## MODIFIED Requirements

### Requirement: The issue body holds the job record
The store SHALL keep an Item's job record in a block `<!-- devops-roadmap-record {...} -->` at the end of the issue body. The body that the store returns SHALL hold no such block, and a body write SHALL keep the issue's block. A block that is not a JSON object SHALL read as an empty record. Only a comment that is the last block of the body SHALL be the record block: a quote of the block in a code span or a code block, and a comment that more text follows, SHALL stay in the body, SHALL read as no record and SHALL log no warning.

#### Scenario: A body write keeps the record
- **WHEN** refine writes a new body to an Item whose job record holds a mark
- **THEN** the body that the store returns is the new body, and the job record still holds the mark

#### Scenario: A person breaks the block
- **WHEN** the record block of an issue holds text that is not JSON
- **THEN** the store reads the issue with an empty job record

#### Scenario: A body quotes the record format
- **WHEN** the body of an issue quotes the record block in a code span, a fenced code block or an indented code block, or holds the comment before more text
- **THEN** the store returns the body with the quote, reads an empty job record, logs no warning, and the next write of the record keeps the quote

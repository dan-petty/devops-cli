## ADDED Requirements

### Requirement: Only the comment at the end of the body is the record block
The store SHALL read as the job record block only a comment that is the last block of the issue body. A quote of the block in a code span or a code block, and a comment that more text follows, SHALL stay in the body, SHALL read as no record and SHALL log no warning.

#### Scenario: A body quotes the record format
- **WHEN** the body of an issue quotes the record block in a code span, a fenced code block or an indented code block, or holds the comment before more text
- **THEN** the store returns the body with the quote, reads an empty job record, logs no warning, and the next write of the record keeps the quote

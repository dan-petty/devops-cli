## MODIFIED Requirements

### Requirement: Only the comment at the end of the body is the record block
The store SHALL read as the job record block only a comment that is the last block of the issue body. A person can open a fence, or an HTML block that only an end text ends, above the record block. Then the store SHALL read a record block with a JSON object on the last line of the body. Each other quote of the block in a code span or a code block, and a comment that more text follows, SHALL stay in the body, SHALL read as no record and SHALL log no warning.

#### Scenario: A body quotes the record format
- **WHEN** the body of an issue quotes the record block in a code span, a fenced code block or an indented code block, or holds the comment before more text
- **THEN** the store returns the body with the quote, reads an empty job record, logs no warning, and the next write of the record keeps the quote

#### Scenario: A person opens a block above the record
- **WHEN** a person opens a backtick fence, a tilde fence, a `<pre>` block or a comment above the record block that a job wrote, and does not close it
- **THEN** the store reads the record, and the body that it gives is the body of the person without the record block

#### Scenario: The next write closes the block of the person
- **WHEN** a job writes a mark to an issue in which a person opened a block above the record block
- **THEN** CommonMark parses the record block of the written body as its last HTML block, the record holds the keys of the old record and the mark, the body holds one record block, and the text of the person keeps its rendered form

#### Scenario: A fence above a job block and the record
- **WHEN** a person opens a fence above the refine block and the record block, and a job then writes a mark
- **THEN** the body holds one record block with the keys of the old record and the mark, and a read finds the same section

#### Scenario: A quote in an open block that holds no JSON object
- **WHEN** the last line of a body is a quote of the record block that holds no JSON object, in a fence that the body leaves open
- **THEN** the store returns the body with the quote, reads an empty job record and logs no warning

#### Scenario: The GitHub store keeps the record below an open block
- **WHEN** the GitHub store writes two marks from one read of an issue in which a person opened a fence above the record block
- **THEN** it sends one `PATCH` for each mark, the record holds the keys of the old record and both marks, and `devops_cli_roadmap_record_lost_edit_total` does not change

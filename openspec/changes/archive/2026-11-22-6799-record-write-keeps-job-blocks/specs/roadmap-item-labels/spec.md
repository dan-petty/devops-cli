## MODIFIED Requirements

### Requirement: A record write closes the block that the body leaves open
A body can end inside a fenced code block, or an HTML block that only an end text ends, such as a comment or `<pre>`. Then the store SHALL put the close of that block on a line of its own before the record block. When job blocks end that block for a read, the close SHALL go before the first of them. The record block SHALL stay the last block of the body. The close SHALL add no empty line to the block. A body with no open block SHALL get no close. The close SHALL count as no edit of a person.

#### Scenario: A body ends in an open block
- **WHEN** a job writes a mark to an issue whose body ends in an open backtick fence, an open tilde fence, an open `<!--` or an open `<pre>`
- **THEN** the store reads the mark back, and the body that it gives is the body with the close of the block on a line of its own after it

#### Scenario: A job block at the end of an open block
- **WHEN** a job writes a mark to an issue whose body has the refine block at the end of an open fence or an open `<pre>` of a person
- **THEN** the store puts the close before the start marker, and a read of the written body finds the same section and the mark

#### Scenario: A body with no open block
- **WHEN** the store writes a record block after a body that leaves no block open
- **THEN** the text that it writes is the body, a blank line and the record block, as before

#### Scenario: The next rounds see no change
- **WHEN** a job writes the hash of the body after each round in which the hash differs from the recorded hash, four rounds in a row, on a body that ends in an open fence
- **THEN** only the first two rounds see a change, and the body holds one record block

#### Scenario: The GitHub store counts no lost edit for the close
- **WHEN** the GitHub store writes two marks from one read of the item to a body that ends in an open fence
- **THEN** it sends one `PATCH` for each mark, the record holds both marks, and `devops_cli_roadmap_record_lost_edit_total` does not change

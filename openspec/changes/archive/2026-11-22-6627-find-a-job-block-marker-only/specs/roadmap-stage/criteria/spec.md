## ADDED Requirements

### Requirement: The refine block starts and ends at an HTML block marker
The stage job SHALL cut the refine block from the body only at a start marker and an end marker that CommonMark parses as an HTML block each, and SHALL read no block from a start marker with no end marker. A marker that a person quotes in a code span, a code block or a paragraph SHALL stay in the text that the job reads.

#### Scenario: A body that quotes both refine markers
- **WHEN** a body quotes the refine start marker and the refine end marker in code spans, holds an acceptance criterion between them, and holds a bullet that names a path between them under another heading
- **THEN** `acceptance_criteria` returns that criterion, `refine_decisions` returns no decision, and `requirement_lines` returns the path of that bullet as a requirement line

#### Scenario: A real refine block is cut
- **WHEN** a body holds a refine block whose start marker and end marker are each an HTML block on a line of its own, with a `Chosen` line inside
- **THEN** `refine_decisions` returns that decision and the acceptance criteria outside the block are read

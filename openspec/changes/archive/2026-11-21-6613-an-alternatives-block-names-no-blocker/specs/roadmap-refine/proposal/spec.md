## MODIFIED Requirements

### Requirement: The body's answered key questions are not asked again
Refine SHALL read the body's "Key questions" section as CommonMark, up to the next heading of the same or a higher level or the start or the end marker of a job block. Only a top-level list item whose first paragraph holds a question mark SHALL be a question. Text after its last question mark, or a block inside the item after that paragraph, SHALL answer it. Refine SHALL send the other questions numbered, and a number that no answer names SHALL be an open question.

#### Scenario: A body that answers its own questions
- **WHEN** the body's "Key questions" hold "- *Which ADR number?* (proposed) The next free one.", "- *Which files?*" with an indented answer under it, and "- #1336 owns the directory."
- **THEN** refine sends no body question and reports no open question

#### Scenario: A body question that no answer names
- **WHEN** the body's "Key questions" hold "- *Which store holds the record?*" and no answer names number 1
- **THEN** "*Which store holds the record?*" is an open question

#### Scenario: A question that wraps, and a paragraph after the list
- **WHEN** the body's "Key questions" hold "- How should refine handle a body" with "that wraps across lines?" on the next line, then a blank line and the paragraph "Context: the Service writes it hourly."
- **THEN** "How should refine handle a body that wraps across lines?" is the one body question

#### Scenario: An alternatives block after the key questions
- **WHEN** the body's "Key questions" hold "- *Which store holds the record?*", and the next line, with no heading between, is the start marker of an alternatives block whose Lacks list holds "- Which parser reads the marker?"
- **THEN** "*Which store holds the record?*" is the one body question

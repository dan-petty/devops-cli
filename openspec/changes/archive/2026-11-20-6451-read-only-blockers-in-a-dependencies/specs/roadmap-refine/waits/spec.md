## ADDED Requirements

### Requirement: A blocker line under Dependencies names a dependency
Refine SHALL read as a dependency only a line under the Dependencies heading that names blockers: a line that starts with a blocker opener in any case (`Merge first`, `Depends on`, `Blocked by`, `Waits for`, `Wait for`), or a line whose first word is an issue reference when it is the first text of a list item or a paragraph outside a list. Refine SHALL read no other `#N` of the section, such as a parent, a child, a related issue or the source line of intake.

#### Scenario: A source line after None
- **WHEN** `body_dependencies` reads a body whose Dependencies section holds `None.` and then `Source: #4989` as a separate paragraph
- **THEN** `body_dependencies` returns an empty list

#### Scenario: A parent, a child, a related issue and a reverse link
- **WHEN** `body_dependencies` reads a body whose Dependencies section holds the paragraphs `Part of #5014`, `Child 5 of #4893`, `Related: #4408`, `#4691 needs this item` and `This item blocks #5134 step 6`
- **THEN** `body_dependencies` returns an empty list

#### Scenario: A blocker list item, a line of references and a Merge first line
- **WHEN** `body_dependencies` reads a body whose Dependencies section holds the list item `- #4989`, the paragraph `#5134, #5135` and the paragraph `Merge first: #5136`
- **THEN** `body_dependencies` returns `[4989, 5134, 5135, 5136]` in the order of the section

#### Scenario: A paragraph that opens with references and goes on in prose
- **WHEN** `body_dependencies` reads a body whose Dependencies section holds the paragraph `#4884, #4889, #3917. The scheduled reindex waits for #4566.`
- **THEN** `body_dependencies` returns `[4884, 4889, 3917, 4566]`

#### Scenario: A Depends on line
- **WHEN** `body_dependencies` reads a body whose Dependencies section holds the paragraph `Depends on #5356. The acceptance needs the running server.` and then the paragraph `It does not wait for #5343.`
- **THEN** `body_dependencies` returns `[5356]`

### Requirement: A reverse phrase or a parent names no blocker
On a blocker line, a clause that holds a reverse phrase in any case (`needs this item`, `waits for this item`, `depends on this item`, `blocked by this item`) SHALL name no blocker; a clause ends at `.`, `;`, `!` or `?`. Refine SHALL read each other issue reference except one that directly follows `of`, which names a parent.

#### Scenario: A reverse phrase
- **WHEN** `body_dependencies` reads a body whose Dependencies section holds the list items `- #3741 (the backup sets the pattern).` and `- #3803 (move the database) waits for this item.`
- **THEN** `body_dependencies` returns `[3741]`

#### Scenario: A blocker and a reverse clause in one paragraph
- **WHEN** `body_dependencies` reads a body whose Dependencies section holds the paragraph `#4550 puts the dependencies of the catalog first. #4691 needs this item.`
- **THEN** `body_dependencies` returns `[4550]`

#### Scenario: A parent after of on a blocker line
- **WHEN** `body_dependencies` reads a body whose Dependencies section holds the paragraph `Merge first: #4835, child 8 of #4833.`
- **THEN** `body_dependencies` returns `[4835]`

### Requirement: A non-blocker mention under Dependencies holds nothing back
The stage job and the implement job SHALL give no reason for an open issue that the body names only as a non-blocker mention under Dependencies. They SHALL name only an open issue that a blocker line of the section names.

#### Scenario: An open related issue
- **WHEN** the Dependencies section of a Ready item holds `Related: #4408`, and issue `#4408` is open
- **THEN** the stage job and the implement job give no reason for the item, and neither reason names `#4408`

#### Scenario: An open issue on a Depends on line
- **WHEN** the Dependencies section of a Ready item holds `Depends on #4408`, and issue `#4408` is open
- **THEN** the stage job and the implement job give the reason that names `#4408`

## ADDED Requirements

### Requirement: A blocker line under Dependencies names a dependency
Refine SHALL read as a dependency of the proposal only a line under the Dependencies heading of the body that names a blocker: a list item whose first word is an issue reference, a line that holds issue references only, or a line that starts with `Merge first`. Refine SHALL read no other `#N` of the section as a dependency, such as a parent, a child, a related issue, an issue that waits for this item, or the source line of intake.

#### Scenario: A source line after None
- **WHEN** `body_dependencies` reads a body whose Dependencies section holds `None.` and then `Source: #4989` as a separate paragraph
- **THEN** `body_dependencies` returns an empty list

#### Scenario: A parent, a child, a related issue and a reverse link
- **WHEN** `body_dependencies` reads a body whose Dependencies section holds the paragraphs `Part of #5014`, `Child 5 of #4893`, `Related: #4408`, `#4691 needs this item` and `This item blocks #5134 step 6`
- **THEN** `body_dependencies` returns an empty list

#### Scenario: A blocker list item, a line of references and a Merge first line
- **WHEN** `body_dependencies` reads a body whose Dependencies section holds the list item `- #4989`, the paragraph `#5134, #5135` and the paragraph `Merge first: #5136`
- **THEN** `body_dependencies` returns `[4989, 5134, 5135, 5136]` in the order of the section

### Requirement: A non-blocker mention under Dependencies holds nothing back
The stage job and the implement job SHALL give no reason for an open issue that the body names only as a non-blocker mention under Dependencies. They SHALL name only an open issue that a blocker line of the section names.

#### Scenario: An open related issue
- **WHEN** the Dependencies section of a Ready item holds `Related: #4408`, and issue `#4408` is open
- **THEN** the stage job and the implement job give no reason for the item, and neither reason names `#4408`

## ADDED Requirements

### Requirement: An issue reference under Dependencies names a blocker
Refine SHALL read each `#N` under the Dependencies heading of the body as a dependency of the proposal, also in a sentence of prose, unless the requirement "A link under Dependencies names no blocker" leaves it out.

#### Scenario: A blocker list item, a line of references and a Merge first line
- **WHEN** `body_dependencies` reads a body whose Dependencies section holds the list item `- #4989`, the paragraph `#5134, #5135` and the paragraph `Merge first: #5136`
- **THEN** `body_dependencies` returns `[4989, 5134, 5135, 5136]` in the order of the section

#### Scenario: A paragraph that opens with references and goes on in prose
- **WHEN** `body_dependencies` reads a body whose Dependencies section holds the paragraph `#4884, #4889, #3917. The scheduled reindex waits for #4566.`
- **THEN** `body_dependencies` returns `[4884, 4889, 3917, 4566]`

#### Scenario: A Depends on line
- **WHEN** `body_dependencies` reads a body whose Dependencies section holds the paragraph `Depends on #5356. The acceptance needs the running server.` and then the paragraph `It does not wait for #5343.`
- **THEN** `body_dependencies` returns `[5356]`

#### Scenario: A blocker in a sentence that opens with other words
- **WHEN** `body_dependencies` reads a body whose Dependencies section holds the paragraphs `#5421 (merged first).` and `Open the pull request after the pull request of #5234 merges.`
- **THEN** `body_dependencies` returns `[5421, 5234]`

#### Scenario: The hold line of the freeze
- **WHEN** `body_dependencies` reads a body whose Dependencies section holds as its first item `- #6521 (hold: incremental work on the stage, implement and fix-checks jobs waits for the re-architecture of #6519)`
- **THEN** `body_dependencies` returns `[6521]`

### Requirement: A link under Dependencies names no blocker
Refine SHALL read no dependency from a block that starts with `None` or `No`, from a `#N` after a link word of its sentence (`Part of`, `Child`, `Tracker`, `Related`, `Source` or an owner decision), from a sentence with a reverse phrase such as `needs this item`, `this item blocks` or `is the parent`, from a block whose issue merges in either order, or from a `#N` in parentheses with other words. A sentence ends at `.`, `;`, `!`, `?` or a line end.

#### Scenario: A source line after None
- **WHEN** `body_dependencies` reads a body whose Dependencies section holds `None.` and then `Source: #4989` as a separate paragraph
- **THEN** `body_dependencies` returns an empty list

#### Scenario: A parent, a child, a related issue and a reverse link
- **WHEN** `body_dependencies` reads a body whose Dependencies section holds the paragraphs `Part of #5014`, `Child 5 of #4893`, `Related: #4408`, `#4691 needs this item` and `This item blocks #5134 step 6`
- **THEN** `body_dependencies` returns an empty list

#### Scenario: A blocker and a reverse sentence in one paragraph
- **WHEN** `body_dependencies` reads a body whose Dependencies section holds the paragraph `#4550 puts the dependencies of the catalog first. #4691 needs this item.`
- **THEN** `body_dependencies` returns `[4550]`

#### Scenario: A parent after a blocker, a parent tracker and a merge in either order
- **WHEN** `body_dependencies` reads a body whose Dependencies section holds the paragraph `Merge first: #4835, child 8 of #4833.` and the list items `- #4517 is the parent tracker.` and `- #6347 (open): changes the verdict too. Rebase before the second of the two merges.`
- **THEN** `body_dependencies` returns `[4835]`

### Requirement: A non-blocker mention under Dependencies holds nothing back
The stage job and the implement job SHALL give no reason for an open issue that the body names only as a non-blocker mention under Dependencies. They SHALL name only an open issue that the section names as a blocker.

#### Scenario: An open related issue
- **WHEN** the Dependencies section of a Ready item holds `Related: #4408`, and issue `#4408` is open
- **THEN** the stage job and the implement job give no reason for the item, and neither reason names `#4408`

#### Scenario: An open issue on a Depends on line
- **WHEN** the Dependencies section of a Ready item holds `Depends on #4408`, and issue `#4408` is open
- **THEN** the stage job and the implement job give the reason that names `#4408`

#### Scenario: A held item
- **WHEN** the Dependencies section of an item holds the hold line `- #<hold> (hold: ... of #<tracker>)` and then `Related: #<related>`, and the three issues are open
- **THEN** `open_dependency` gives a reason that names `#<hold>` only

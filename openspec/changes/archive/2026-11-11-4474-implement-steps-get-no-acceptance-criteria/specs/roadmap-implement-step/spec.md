## ADDED Requirements

### Requirement: The issue section of a step holds the refined criteria and no HTML comment
The issue section of the user message of a step SHALL hold the title of the item and each top-level section of the issue body whose heading is `Problem or Motivation`, `Problem statement` or `Acceptance criteria`, or starts with `Requirement:`, each with its deeper headings, in the order of the body. The section SHALL hold no top-level HTML comment block of the body. An issue body that holds none of these sections SHALL give its whole text with no top-level HTML comment block.

#### Scenario: A body that refine wrote its criteria into
- **WHEN** the body holds a `### Acceptance criteria` heading that two `### Requirement:` sections with their `#### Scenario:` lines follow, at the same level
- **THEN** the issue section holds both requirement headings, their text and their `WHEN` and `THEN` lines after the `Acceptance criteria` heading

#### Scenario: The refine markers after a criteria list of a person
- **WHEN** the body holds a `## Acceptance criteria` list and then the refine start marker and the `checked-at` comment before `## Proposed design`
- **THEN** the issue section holds the list items and no `<!--`

#### Scenario: A body with no wanted section
- **WHEN** the body holds only the sections of the bug form and the alternatives block
- **THEN** the issue section holds the whole body without the two marker lines of the alternatives block

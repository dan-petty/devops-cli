## ADDED Requirements

### Requirement: A job block marker ends the Dependencies section
Refine SHALL read the Dependencies section of the body up to the next heading of the same or a higher level, or up to an HTML block that is the start or the end marker of a job block (`devops-roadmap-refine` or `devops-roadmap-alternatives`), whichever comes first. A heading inside a job block SHALL start a section. A marker in a code span or inside a paragraph SHALL NOT end the section.

#### Scenario: An alternatives block after the Dependencies section
- **WHEN** `body_dependencies` reads a body whose Dependencies section holds `None.`, and the next line, with no heading between, is the start marker of an alternatives block whose Lacks list holds `- Two-container template integration that #5506 adds`
- **THEN** `body_dependencies` returns an empty list

#### Scenario: The Dependencies part of the refine block
- **WHEN** `body_dependencies` reads a body with no Dependencies heading outside the refine block, the `### Dependencies` part of the refine block holds `- #4989` and is the last part of the block, and an alternatives block whose Lacks list holds `- A tool that #5506 adds` follows the refine end marker
- **THEN** `body_dependencies` returns `[4989]`

#### Scenario: Person text after the refine end marker
- **WHEN** `body_dependencies` reads a body with no alternatives block, the `### Dependencies` part of the refine block holds `- #4989` and is the last part of the block, and the paragraph `Depends on #8888.` follows the refine end marker
- **THEN** `body_dependencies` returns `[4989]`

#### Scenario: A Dependencies section after the end marker of an alternatives block
- **WHEN** `body_dependencies` reads a body that holds an alternatives block whose Lacks list holds `- A tool that #5506 adds`, and after its end marker the heading `## Dependencies` and the list item `- #4989`
- **THEN** `body_dependencies` returns `[4989]`

#### Scenario: A marker in a code span
- **WHEN** `body_dependencies` reads a body whose Dependencies section holds a paragraph that quotes the start marker of an alternatives block in a code span (`CONST_ROADMAP_ALTERNATIVES_START_MARKER`), and then the list item `- #4989`
- **THEN** `body_dependencies` returns `[4989]`

## ADDED Requirements

### Requirement: Implement section text stops at job block markers
The section readers used by `issue_inputs` (`section_text` in `src/devops_cli/roadmap/step_files.py`) SHALL end an open section at any top-level job block marker (`block_marker_of`), and `issue_inputs` SHALL run `section_text` before removing HTML comments so job block text does not leak into the matched issue sections.

#### Scenario: Job blocks follow the last person section
- **WHEN** `issue_inputs` reads an item whose `Acceptance criteria` section is followed by an alternatives block or a refine block start marker
- **THEN** the returned issue inputs exclude text from the alternatives block and non-requirement text from the refine block

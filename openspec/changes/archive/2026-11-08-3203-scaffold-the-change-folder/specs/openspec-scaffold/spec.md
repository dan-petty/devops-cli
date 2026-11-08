## Purpose
Scaffold an OpenSpec change folder in project form for an issue with pre-filled templates.

## ADDED Requirements

### Requirement: The command creates the change folder
`devops openspec new` SHALL create an OpenSpec change folder named `<issue>-<slug>` containing `.openspec.yaml`, `proposal.md`, `design.md`, and `tasks.md` in project form.

#### Scenario: Scaffold a new change
- **WHEN** an author runs `devops openspec new 3203 --title 'feat(openspec): scaffold the change folder'`
- **THEN** `openspec/changes/3203-scaffold-the-change-folder/` is created with the four files

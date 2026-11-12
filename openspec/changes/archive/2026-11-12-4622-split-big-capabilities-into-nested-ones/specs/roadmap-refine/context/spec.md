## ADDED Requirements

### Requirement: The context reads a nested capability
The context SHALL take each `spec.md` at any depth under `openspec/specs/` as the capability of its folder path. A nested capability `<area>/<name>` SHALL cover a module when its area covers that module by name, and SHALL cover a file when its text names the path of the file.

#### Scenario: A cited module has a nested capability of its name
- **WHEN** an item cites `src/devops_cli/widget/render.py`, and `openspec/specs/widget-render/output/spec.md` holds one requirement, and `openspec/specs/other/nested/spec.md` holds one
- **THEN** the context holds the section "Requirements of widget-render/output" with its name, and no name from `other/nested`

#### Scenario: A nested capability names the path of a cited file
- **WHEN** an item cites `src/devops_cli/widget/render.py`, and the text of `openspec/specs/named/by-path/spec.md` names that path
- **THEN** the context holds the section "Requirements of named/by-path" with its name

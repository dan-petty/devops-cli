## ADDED Requirements

### Requirement: A task group writes no living spec
A `StageGroup` SHALL reject a path under `openspec/specs/` in `changes` or in `creates`, with a validation error that names the path and says that only `openspec archive` writes living specs. A path under `openspec/specs/` in `reads` SHALL stay accepted.

#### Scenario: A group lists a living spec in changes
- **WHEN** A `StageGroup` lists `openspec/specs/config-commands/spec.md` in `changes` and `creates`
- **THEN** validation fails, and the error names `openspec/specs/config-commands/spec.md` and says that only `openspec archive` writes living specs

#### Scenario: A group lists a living spec in creates
- **WHEN** A `StageGroup` lists `openspec/specs/new-capability/spec.md` in `changes` and `creates`
- **THEN** validation fails, and the error names `openspec/specs/new-capability/spec.md`

#### Scenario: A group writes a source file and reads a living spec
- **WHEN** A `StageGroup` lists `src/devops_cli/sample.py` in `changes` and `openspec/specs/config-commands/spec.md` in `reads`
- **THEN** validation succeeds

### Requirement: The stage prompt states the living-spec rule
The stage prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` SHALL state that a task group never puts a path under `openspec/specs/` in `changes` or in `creates`, and that `openspec archive` writes living specs.

#### Scenario: The prompt holds the living-spec rule
- **WHEN** a test reads `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- **THEN** the text says that a task group must not change or create a file under `openspec/specs/`, and that `openspec archive` writes living specs

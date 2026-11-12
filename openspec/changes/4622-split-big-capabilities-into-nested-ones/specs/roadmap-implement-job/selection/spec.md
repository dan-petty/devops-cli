## ADDED Requirements

### Requirement: The plan check reads a nested capability
The plan reader SHALL read a spec file at any depth under `openspec/specs/` of a commit, and a spec delta at any depth under `specs/` of a change folder, as the capability of its folder path, such as `roadmap-stage/paths-gate`.

#### Scenario: The base specs of a commit hold a nested capability
- **WHEN** a commit holds `openspec/specs/roadmap-stage/paths-gate/spec.md` with the requirement "A path exists"
- **THEN** the base specs of the commit hold the capability `roadmap-stage/paths-gate` with that requirement

#### Scenario: A plan with a delta of a nested capability
- **WHEN** a change folder holds `specs/roadmap-stage/paths-gate/spec.md`
- **THEN** the reader gives the spec delta of the capability `roadmap-stage/paths-gate`

## ADDED Requirements

### Requirement: Refuse a spec delta that the changed paths do not need
`check_proposal` SHALL refuse a proposal with `skip_specs: false` when every path of every group's `changes` starts with `tests/`, `.github/workflows/`, `docs/` or `openspec/`.

#### Scenario: Every changed path is a test, CI, document or plan path
- **WHEN** A proposal has `skip_specs: false` and every `changes` path starts with `tests/`, `.github/workflows/`, `docs/` or `openspec/`
- **THEN** `check_proposal` returns a problem that says no spec delta is needed

#### Scenario: One changed path is source code
- **WHEN** A proposal has `skip_specs: false` and one `changes` path starts with `src/`
- **THEN** `check_proposal` returns no problem about the spec delta

### Requirement: Refuse an added requirement that the base spec already has
`check_proposal` SHALL refuse an ADDED requirement whose name equals the name of a requirement in the base spec of that capability.

#### Scenario: An added requirement name is in the base spec
- **WHEN** A spec delta ADDs a requirement whose name is a requirement name of `openspec/specs/<capability>/spec.md`
- **THEN** `check_proposal` returns a problem that names the duplicate requirement

#### Scenario: An added requirement name is new
- **WHEN** A spec delta ADDs a requirement whose name is in no requirement of the base spec of that capability
- **THEN** `check_proposal` returns no problem about a duplicate

### Requirement: The model input holds the purpose and the requirement names of each capability
The stage job SHALL give the model the purpose and the requirement names of every capability under `openspec/specs/`.

#### Scenario: The input lists a capability
- **WHEN** The stage job builds the model input for a proposal
- **THEN** the input holds the purpose and the requirement names of each capability

## MODIFIED Requirements

### Requirement: Refuse a spec delta that the changed paths do not need
`check_proposal` SHALL refuse a proposal with `skip_specs: false` when every path of every group's `changes` is under `tests/`, `.github/workflows/`, `docs/`, `openspec/` or `src/devops_cli/ai/knowledge_base/`, or is a markdown document outside `src/`.

#### Scenario: Every changed path is a test, CI, document or plan path
- **WHEN** A proposal has `skip_specs: false` and every `changes` path starts with `tests/`, `.github/workflows/`, `docs/` or `openspec/`
- **THEN** `check_proposal` returns a problem that says no spec delta is needed

#### Scenario: One changed path is source code
- **WHEN** A proposal has `skip_specs: false` and one `changes` path starts with `src/`
- **THEN** `check_proposal` returns no problem about the spec delta

#### Scenario: Root documents with a delta
- **WHEN** A plan changes only `SECURITY.md` and `CONTRIBUTING.md` and gives a spec delta
- **THEN** `check_proposal` reports that these paths need no spec delta

#### Scenario: Knowledge-base file and test path with a delta
- **WHEN** A plan changes only `src/devops_cli/ai/knowledge_base/example.md` and a path under `tests/`, and gives a spec delta
- **THEN** `check_proposal` reports that these paths need no spec delta

#### Scenario: Knowledge-base file and test path without a delta
- **WHEN** A plan changes only `src/devops_cli/ai/knowledge_base/example.md` and a path under `tests/`, and sets `skip_specs: true`
- **THEN** `check_proposal` reports no problem about a spec delta

#### Scenario: Task prompt with a delta
- **WHEN** A plan changes only `src/devops_cli/ai/tasks/roadmap_stage_change.md` and gives a spec delta
- **THEN** `check_proposal` reports no problem about a spec delta

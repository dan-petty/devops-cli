# Tasks

## 1. Requirement length check in OpenSpec gate

> Kind: behavior

- [x] 1.1 Write failing tests in `tests/openspec/test_openspec_gate.py` covering long `MODIFIED` and `ADDED` requirements, shared `REQUIREMENT_MAX_CHARS` / helper identity, UTF-16 surrogate pair length `502`, archived changes out of scope, and the `openspec` CI row failure
  - Verification: `$ uv run devops ci test tests/openspec/test_openspec_gate.py tests/openspec/test_openspec_tool.py tests/roadmap/stage/test_roadmap_stage_requirement_length.py tests/commands/test_config_workspace_docs_dry_run.py`
- [x] 1.2 Export `requirement_length_problem` in `src/devops_cli/roadmap/stage/stage_change.py`, read deltas once in `src/devops_cli/openspec/overlap.py`, enforce `GateCheck.REQUIREMENT_LENGTH` before CLI validation in `src/devops_cli/openspec/gate.py`, and defer gate imports inside `src/devops_cli/commands/openspec.py` so `devops openspec --help` passes startup import budgets
  - Verification: `$ uv run devops ci test tests/openspec/test_openspec_gate.py tests/openspec/test_openspec_tool.py tests/roadmap/stage/test_roadmap_stage_requirement_length.py tests/commands/test_config_workspace_docs_dry_run.py`

## 2. Gate and quality verification

> Kind: verification

- [x] 2.1 Verify startup-imports, openspec gate, lint, typecheck, and test-tree checks pass
  - Verification: `$ uv run devops ci --check --no-cache --only startup-imports,openspec,typecheck,lint,format,test-tree`

Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

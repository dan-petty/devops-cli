## MODIFIED Requirements

### Requirement: A fix that changes no source code needs no proof
`devops ci fail-to-pass` SHALL pass with no replay, and SHALL say that the fix changes no source code and no gate check, when the diff from the merge base holds no `.py` file under `src/` outside the knowledge base and no check module of `tests/gate/*_checks/`.

#### Scenario: A fix of a prompt
- **WHEN** a fix changes only `src/devops_cli/ai/tasks/roadmap_stage_change.md` and a test that passes on base
- **THEN** the command exits 0, starts no pytest, and says that the fix changes no source code

#### Scenario: A fix of tool pins
- **WHEN** a fix changes only `src/devops_cli/tools_lock/tools.lock` and `src/devops_cli/tools_lock/devcontainers-cli/package-lock.json`
- **THEN** the command exits 0 and starts no pytest

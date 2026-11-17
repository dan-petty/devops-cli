## MODIFIED Requirements

### Requirement: The check runs only for a fix that changes the code under src or a gate check
The fail-to-pass workflow SHALL start only for a pull request into `main` that changes a `.py` file under `src/` outside `src/devops_cli/ai/knowledge_base/`, or a path under `tests/gate/*_checks/`, and its job SHALL run only for a title that `CONST_DEFECT_TITLE_PATTERN` reads as a fix and an author that is not `dan-petty-renovate[bot]`. Its comment MUST say that a changed gate check can fail on the base, and that a prompt, a pin or other data under `src/` is no code.

#### Scenario: A pull request that is not a fix
- **WHEN** the job condition of `.github/workflows/fail-to-pass.yml` is evaluated for the titles `feat(ci): add a check`, `docs(ci): describe the check`, `chore(main): release 1.0.0` and `fixup: squash a commit`
- **THEN** the job does not run for any of them

#### Scenario: A fix title
- **WHEN** the job condition is evaluated for `fix(ci): replay the changed tests`, `fix: replay the changed tests` and `FIX(ci): replay the changed tests`
- **THEN** the job runs for each of them

#### Scenario: A dependency bump of the Renovate App
- **WHEN** the job condition is read
- **THEN** it holds `github.event.pull_request.user.login != 'dan-petty-renovate[bot]'` and names no other author, so the fix pull requests of the Service App keep the check

#### Scenario: A change outside the code under src
- **WHEN** the path filter of the workflow is evaluated for `tests/test_fail_to_pass.py`, `tests/gate/runner.py`, `k8s/otel/values.yaml`, `Dockerfile`, `src/devops_cli/ai/knowledge_base/devops_cli/tasks/testing.md`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/tools_lock/tools.lock` and the files of a release pull request
- **THEN** the workflow does not start for any of them, and it starts for `src/devops_cli/ci/fail_to_pass.py`

#### Scenario: A gate check pull request
- **WHEN** the path filter of the workflow is evaluated for `tests/gate/k8s_checks/otel_collector.py`
- **THEN** the workflow starts, and the comment of the workflow names `tests/gate/*_checks/` and holds no sentence that only `src/` can make a test fail on base

## ADDED Requirements

### Requirement: A fix that changes no source code needs no proof
`devops ci fail-to-pass` SHALL pass with no replay, and SHALL say that the fix changes no source code and no gate check, when the diff from the merge base holds no `.py` file under `src/` outside the knowledge base and no check module of `tests/gate/*_checks/`.

#### Scenario: A fix of a prompt
- **WHEN** a fix changes only `src/devops_cli/ai/tasks/roadmap_stage_change.md` and a test that passes on base
- **THEN** the command exits 0, starts no pytest, and says that the fix changes no source code

#### Scenario: A fix of tool pins
- **WHEN** a fix changes only `src/devops_cli/tools_lock/tools.lock` and `src/devops_cli/tools_lock/openspec/package-lock.json`
- **THEN** the command exits 0 and starts no pytest

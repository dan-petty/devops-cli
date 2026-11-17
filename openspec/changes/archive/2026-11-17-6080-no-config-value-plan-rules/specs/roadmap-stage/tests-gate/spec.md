## REMOVED Requirements

### Requirement: A new test module sits in a mirror directory
**Reason**: It admitted any new test module in `tests/invariants/`, the folder that held most of the tests that read a manifest or a config file (#6080).
**Migration**: The requirement "A new test module sits in the mirror of its source code" holds the rule.

## ADDED Requirements

### Requirement: A new test module sits in the mirror of its source code
`check_proposal` SHALL refuse a path in `creates` that is a test module under `tests/` unless it is in the directory that mirrors the package of a source file that the plan changes. When the plan changes no source file, it SHALL refuse a test module directly under `tests/` or in `tests/invariants/`.

#### Scenario: A flat test path is refused
- **WHEN** a group creates `tests/test_stage.py` and the plan changes `src/devops_cli/roadmap/stage.py`
- **THEN** `check_proposal` returns a problem that names the path and the directory `tests/roadmap`

#### Scenario: A mirrored test path is accepted
- **WHEN** a group creates `tests/roadmap/test_stage.py` and the plan changes `src/devops_cli/roadmap/stage.py`
- **THEN** `check_proposal` returns no problem about the test path

#### Scenario: A new invariant test of a source change
- **WHEN** a group creates `tests/invariants/test_k8s_runner.py` and the plan changes `src/devops_cli/roadmap/stage.py`
- **THEN** `check_proposal` returns a problem that names the path and the directory `tests/roadmap`

#### Scenario: A new invariant test of a plan with no source change
- **WHEN** a group creates `tests/invariants/test_k8s_runner.py` and the plan changes only `.github/renovate.json`
- **THEN** `check_proposal` returns a problem that names the path and asks for the folder that mirrors the package of the source code that it tests

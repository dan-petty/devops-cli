## ADDED Requirements

### Requirement: The coverage report of the strength check takes no floor of its own
The coverage run of the strength check SHALL write its report with `coverage xml --fail-under=0`, so that the `fail_under` of `[tool.coverage.report]`, the floor of the whole suite, does not fail a scoped run. diff-cover with `--fail-under 90` SHALL stay the bound of the changed lines.

#### Scenario: A scoped run under the floor of the whole suite
- **WHEN** the scoped test modules cover 17% of `src`, the file sets `fail_under = 85`, and diff-cover finds every changed line covered
- **THEN** the coverage delta passes and holds no log

### Requirement: A change with no source file runs only the assertion scan
When no active changed file of the strength check is a Python file under `src/`, the strength check SHALL run the assertion scan only, SHALL start no mutation run and no coverage run, and SHALL add the note that names the reason to its report.

#### Scenario: A change of a test, a manifest and a prompt
- **WHEN** the changed files are `tests/test_sample.py`, `k8s/runner.yaml` and `src/devops_cli/ai/tasks/step.md`, and the new test asserts
- **THEN** the strength check passes, no `pytest`, `coverage` or `mutmut` command starts, and the report holds the note

## REMOVED Requirements

### Requirement: A test path in a docstring or a spec names a file of the commit
**Reason**: The plan cannot change the base docstring of a file that it changes, so a missing test path in that text refused the plan in each repair reply (#4791).
**Migration**: The requirement "A test path in a spec of the plan names a file of the commit" keeps the check of the spec texts.

## ADDED Requirements

### Requirement: A test path in a spec of the plan names a file of the commit
`check_proposal` SHALL fail when a test file path named in a spec of the plan names no file of the commit, and MUST add each such path to its refusal list. It MUST NOT read test paths from the base text of a file that the plan changes, because the plan cannot change that text.

#### Scenario: A spec names a missing test file
- **WHEN** A spec contains `tests/test_missing_example.py` and that file is absent from the commit.
- **THEN** The check reports `tests/test_missing_example.py` as a missing path.

#### Scenario: A base docstring with a missing test path passes
- **WHEN** A plan changes a Python file whose base docstring names `tests/test_x.py`, the commit does not hold that file, and no spec of the plan names it.
- **THEN** `check_proposal` returns no missing test path problem.

#### Scenario: A text that names a test file of the commit passes
- **WHEN** The scanned text names `tests/roadmap/test_roadmap_limit_classes.py` and the commit holds that file.
- **THEN** The check reports no missing path.

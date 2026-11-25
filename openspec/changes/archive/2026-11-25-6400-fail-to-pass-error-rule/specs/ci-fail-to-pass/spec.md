## MODIFIED Requirements

### Requirement: The report names a repaired test
`devops ci fail-to-pass` SHALL name in its report each test that the fix does not change, that fails or errors on the plain merge base and that passes on the head, and each unchanged test file whose file-level collection error on the plain merge base is followed by at least one head case and only passing head cases for that file, as repaired on the head.

#### Scenario: A repaired test in the report
- **WHEN** an unchanged test fails on base, fails on the plain merge base, and passes on the head
- **THEN** the report holds a line that names the test and says that the head repairs it

#### Scenario: All head cases of a file with a collection error pass
- **WHEN** the base and plain merge base reports hold an error case with the module-path id of an unchanged test file and the head report holds passing cases for each test of that file
- **THEN** `_repaired_and_refused` counts the file as repaired and does not refuse it

## ADDED Requirements

### Requirement: File-level collection error without passing head cases is refused
`_repaired_and_refused` SHALL refuse a file-level collection error when any head case of that file does not pass or when the head report holds no case for that file.

#### Scenario: One head case of the file fails
- **WHEN** the plain merge base report holds an error case with the module-path id of a test file and the head report holds a failing case for one test of that file
- **THEN** `_repaired_and_refused` refuses the file

#### Scenario: The head report has no case for the file
- **WHEN** the plain merge base report holds an error case with the module-path id of a test file and the head report holds no case for that file
- **THEN** `_repaired_and_refused` refuses the file

### Requirement: Documentation states the error rule
The `Fail-to-Pass Evidence` section of `CONTRIBUTING.md` SHALL state that an unchanged test is repaired when it fails or errors on the plain merge base and that a file-level collection error is repaired when every head case of that file passes.

#### Scenario: The documentation check passes
- **WHEN** `uv run devops ci --check --only docs` runs on the branch
- **THEN** the command exits 0 and the docs row reports no stale document

### Requirement: Phase reader follows real pytest
The fail-to-pass test suite SHALL include a test that runs real pytest on a module with a collection error and on tests with setup and teardown errors and asserts the phase (`collection`, `setup`, `teardown`) that `TestCaseOutcome.error_phase` reads from the JUnit XML.

#### Scenario: Real pytest collection and setup errors
- **WHEN** the test runs pytest in a subprocess on a temporary directory that holds a module whose import raises and a test whose fixture raises, then parses the JUnit XML
- **THEN** `TestCaseOutcome.error_phase` reads `'collection'` for the module case and `'setup'` for the fixture setup case

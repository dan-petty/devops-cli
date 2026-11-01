## ADDED Requirements

### Requirement: F401 re-import ceiling check
The CI gate SHALL include a check that runs ruff check --select F401 --ignore-noqa over src/ and fails when the finding count exceeds the ceiling of 14.

#### Scenario: New re-import exceeds ceiling
- **WHEN** A # noqa: F401 import is added to a file in src/ and the finding count becomes 15
- **THEN** The check fails with a message naming the new site

#### Scenario: Count at ceiling passes
- **WHEN** The finding count is 14 or fewer
- **THEN** The check passes with exit code 0

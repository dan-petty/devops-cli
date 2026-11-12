## ADDED Requirements

### Requirement: The test-settings row checks the warning filter
The `test-settings` row of `devops ci` SHALL fail when the `filterwarnings` list of `pyproject.toml` does not start with `"error"`, when an entry after it has no reason comment on its line or on the line above, or when the google-genai `ignore` names no removal version.

#### Scenario: Read a filter list that does not start with the error entry
- **WHEN** A test calls the test-settings check with a root whose first filterwarnings entry is a narrow filter.
- **THEN** The check returns 1 and names the missing error entry.

#### Scenario: Read an exception with no reason
- **WHEN** A test calls the test-settings check with a root where an entry after the error entry has no comment on its line or on the line above.
- **THEN** The check returns 1 and names the entry without a reason.

#### Scenario: Read the google-genai exception
- **WHEN** A test calls the test-settings check with a root where the google-genai ignore names no removal version.
- **THEN** The check returns 1 and names Python 3.17.

### Requirement: An advisory row never fails the gate
`devops ci` MUST exit 0 when only a row marked advisory failed, and its summary MUST label that row advisory, while `devops ci uv-check` MUST still exit 1 when `uv check` exits 1.

#### Scenario: Run the gate with a failed ty diagnostic
- **WHEN** The process fake makes `uv check` exit 1 and a developer runs `devops ci --only uv-check --no-cache`.
- **THEN** The gate exits 0 and its summary labels the row advisory.

#### Scenario: Run the uv-check row alone
- **WHEN** The process fake makes `uv check` exit 1 and a developer runs `devops ci uv-check`.
- **THEN** The command exits 1.

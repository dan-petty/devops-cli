## ADDED Requirements

### Requirement: The command waits for a pending title check
The plan-check command SHALL poll the `Semantic PR title` check until its state is terminal or the wait limit of 120 seconds elapses, at an interval of 5 seconds.

#### Scenario: A pending check becomes a pass
- **WHEN** the first read gives `in_progress` and the next read gives `success`
- **THEN** the command reports no problem and no note for `semantic-pr-title`

#### Scenario: A pending check at the wait limit
- **WHEN** every read within the wait limit gives `in_progress`
- **THEN** the result holds one note for `semantic-pr-title` and no problem for it

#### Scenario: A failed title check
- **WHEN** the check summary holds `semantic-pr-title` with the state `failure`
- **THEN** the result holds a problem that names `semantic-pr-title` and its state

#### Scenario: A successful title check
- **WHEN** the check summary holds `semantic-pr-title` with the state `success`
- **THEN** the result holds no problem that names `semantic-pr-title`

### Requirement: The plan-check job waits for the title job
The `plan-check` job of `.github/workflows/pr-title.yml` SHALL list `semantic-title` in `needs` and SHALL use `!cancelled()` in its condition, with no `always()`.

#### Scenario: The workflow condition
- **WHEN** a test parses `.github/workflows/pr-title.yml`
- **THEN** `plan-check` lists `semantic-title` in `needs`, its condition holds `!cancelled()`, and its condition holds no `always()`

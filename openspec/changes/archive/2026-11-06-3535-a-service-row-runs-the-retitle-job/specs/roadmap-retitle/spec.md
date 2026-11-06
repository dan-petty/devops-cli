## ADDED Requirements

### Requirement: A Service row runs the job
The model lane SHALL hold a row named `retitle` after `refine` and before `stage`, and `DEFAULT_DUE_TABLE` SHALL include it.

#### Scenario: Row order
- **WHEN** `MODEL_LANE_ROWS` is read.
- **THEN** it holds `retitle` between `refine` and `stage`, and `DEFAULT_DUE_TABLE` holds it too.

### Requirement: The row is due by its interval
The `retitle` row SHALL be due on its first run and when its last success is at least `DEFAULT_ROADMAP_RETITLE_INTERVAL_MINUTES` (61) old.

#### Scenario: Due at the interval
- **WHEN** the last success of the row is 61 minutes old, or the row has no success.
- **THEN** `run_due_jobs` lists `retitle` as due.

#### Scenario: Not due before the interval
- **WHEN** the last success of the row is 60 minutes old.
- **THEN** `run_due_jobs` does not list `retitle` as due.

### Requirement: The row plans and applies the retitle job
The `retitle` row SHALL call `plan_retitle` with the model of the retitle job and `limit=DEFAULT_ROADMAP_RETITLE_LIMIT`, then call `apply_retitle` with the plan it got, and SHALL need no clone.

#### Scenario: Row run
- **WHEN** the row runs on a store with an open item whose title summary is longer than 60 characters.
- **THEN** the item gets a title that passes `title_problems`, and the schedule records the success of `retitle`.

### Requirement: Stub table omits the row unless asked
`build_stub_table` SHALL omit the `retitle` row unless a `retitle` runner or `include_retitle=True` asks for it.

#### Scenario: Default stub table
- **WHEN** `build_stub_table()` runs with no `retitle` runner.
- **THEN** the table has no `retitle` row.

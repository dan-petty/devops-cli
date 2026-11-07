## Purpose
How the coverage gate measures branches as well as lines, so a conditional whose other side has no test fails the gate instead of passing it.

## ADDED Requirements

### Requirement: The coverage gate measures branches
The `[tool.coverage.run]` table of `pyproject.toml` SHALL set `branch = true`, so coverage.py measures both sides of each conditional in the gate, in the shards and in `devops ci coverage`.

#### Scenario: The coverage configuration enables branch measurement
- **WHEN** a test loads `pyproject.toml` and reads the `[tool.coverage.run]` table
- **THEN** the table sets `branch = true`, `data_file = ".data/.coverage"` and `parallel = true`

#### Scenario: The floor stays the owner's figure
- **WHEN** a test reads the `[tool.coverage.report]` table of `pyproject.toml`
- **THEN** the table sets `fail_under = 85`

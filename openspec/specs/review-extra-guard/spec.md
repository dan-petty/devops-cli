# review-extra-guard Specification

## Purpose

Ensure every test environment installs `lizard` via the `dev` dependency group and fails fast with the install command when absent.

## Requirements

### Requirement: Test environment includes review analyzer
`pyproject.toml` SHALL declare `lizard==1.26.1` in `[dependency-groups] dev` so plain `uv run` test runs install it without `--extra review`.

#### Scenario: Dev dependency group installs lizard
- **WHEN** `uv export --frozen --only-dev --no-emit-project` runs
- **THEN** the exported requirements include `lizard==1.26.1`

### Requirement: Missing lizard invariant names install command
`tests/invariants/test_review_extra_present.py` SHALL fail with `uv sync --all-extras` when `importlib.util.find_spec("lizard")` returns `None`.

#### Scenario: Missing lizard reports sync command
- **WHEN** `importlib.util.find_spec` returns `None` for `lizard`
- **THEN** `_assert_review_extra_present()` raises `AssertionError` matching `uv sync --all-extras`

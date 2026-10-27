# Tasks

## 1. Update

- [x] Pin `dnspython[idna]==2.9.0` in `pyproject.toml` and run `uv lock`
  - Verification: `uv audit` finds no vulnerability
- [x] Run full CI quality checks
  - Verification: `uv run devops ci`

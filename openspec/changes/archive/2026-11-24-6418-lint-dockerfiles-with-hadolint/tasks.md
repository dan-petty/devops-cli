# Tasks

## 1. Behavior

- [x] 1.1 Write failing test for hadolint row command
  - Verification: `$ uv run pytest tests/commands/test_ci_row_commands.py -k hadolint`
- [x] 1.2 Add hadolint hook to pre-commit configuration and add .hadolint.yaml
  - Verification: `$ uv run pre-commit run hadolint --all-files`
- [x] 1.3 Add hadolint check row to devops ci and register in runner tools
  - Verification: `$ uv run devops ci --check --only hadolint`

## 2. Documents

- [x] 2.1 Regenerate CLI reference and documentation
  - Verification: `$ uv run devops docs check`

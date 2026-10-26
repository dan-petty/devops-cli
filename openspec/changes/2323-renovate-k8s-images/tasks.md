# Tasks

## 1. Renovate configuration

- [x] Add the failing test `tests/test_renovate_config.py`
  - Verification: `uv run devops ci test tests/test_renovate_config.py`
- [x] Add the `kubernetes` pattern and the label rule to `.github/renovate.json`
  - Verification: `uv run devops ci test tests/test_renovate_config.py`
- [x] Update the Renovate paragraph in `docs/SDLC.md`
  - Verification: `git diff docs/SDLC.md`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

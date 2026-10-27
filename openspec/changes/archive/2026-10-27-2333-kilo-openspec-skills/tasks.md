# Tasks

## 1. Kilo Code skills

- [x] Extend `tests/test_openspec_scaffold.py` and the OpenSpec fake for the `.kilocode/skills` tree
  - Verification: `uv run devops ci test tests/test_openspec_scaffold.py`
- [x] Add the tree to the generated globs, path classes and pre-commit filter, and commit `.kilocode/skills`
  - Verification: `uv run devops openspec check`
- [x] Update ADR 0010
  - Verification: `uv run devops ci test tests/test_openspec_scaffold.py`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

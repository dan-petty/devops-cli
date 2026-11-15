# Tasks

## 1. Ceilings over all of tests

Reads: `tests/invariants/test_source_tree.py`, `docs/TESTING.md`.

Changes: `tests/invariants/test_source_tree.py`, `docs/TESTING.md`.

- [x] 1.1 Add the two ceilings and their tests.
  - Verification: `$ uv run devops ci test tests/invariants/test_source_tree.py`
- [x] 1.2 Correct the two sentences of the page.
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

# Tasks

## 1. Behavior

- [x] 1.1 Write `tests/invariants/test_review_extra_present.py` and verify `lizard` absence in `dev` group prior to fix
  - Verification: `$ uv run pytest -n 0 tests/invariants/test_review_extra_present.py tests/invariants/test_source_tree.py`
- [x] 1.2 Declare `lizard==1.26.1` in `[dependency-groups] dev` of `pyproject.toml`, update lockfile if needed, and verify `review_window` and `git` gate
  - Verification: `$ uv run pytest -n 0 tests/invariants/test_review_extra_present.py tests/core/test_git_contract.py tests/roadmap/project_review/test_review_facts.py -k 'review_window or test_the_facts_of_a_version_window or review_extra' && uv run devops ci --check --skip test --force`

## 2. Documents

- [x] 2.1 List `test_review_extra_present.py` in `docs/TESTING.md`
  - Verification: `$ uv run pytest -n 0 tests/invariants/test_source_tree.py`

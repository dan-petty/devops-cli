# Tasks

## 1. A publish that runs again

Kind: behavior.

- [x] 1.1 Write failing tests: a new branch after a person deleted the old one gets a new draft; a publish that died before it recorded the draft updates the open draft; a return publish that died after the withdraw returns the item the next time; an issue title with a closing keyword stops the item before the push; the dry-run plan lists the git calls of the three phases and of the withdraw
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_phases.py tests/roadmap/test_roadmap_dry_runs.py`
- [x] 1.2 Write the draft mark in `prepare`, turn on the lookup of the open draft, clear `implement.base` after the withdraw, check the title of the issue for a closing keyword, and list the missing calls in the dry-run plan
  - Verification: `$ uv run devops ci test tests/roadmap/implement tests/roadmap/test_roadmap_dry_runs.py`

## 2. Documents

Kind: other.

- [x] 2.1 Describe the phases in SECURITY.md, the docstrings of `process_hardening.py`, `worktree_add.py` and `stop_clear.py`, the description of `continuations_per_item` and the spec of the pull request, and regenerate the documentation
  - Verification: `$ uv run devops ci docs`

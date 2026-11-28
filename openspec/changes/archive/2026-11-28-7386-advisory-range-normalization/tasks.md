# Tasks

## 1. Normalize advisory ranges and bound open ranges with patched_version

Kind: behavior.

Reads: `src/devops_cli/research/version_match.py`, `src/devops_cli/research/advisories.py`, `tests/research/test_version_match.py`, `tests/research/test_advisories.py`.

Changes: `src/devops_cli/research/version_match.py`, `src/devops_cli/research/advisories.py`, `tests/research/test_version_match.py`, `tests/research/test_advisories.py`.

- [x] 1.1 Write failing tests in `tests/research/test_version_match.py` and `tests/research/test_advisories.py` covering bare versions, leading `v`, `-stable` suffixes, rejected unknown suffixes, `in_range(..., patched_version=...)` on open lower bounds, and `_github_matches` / `find_advisories` with `patched_versions`.
  - Verification: `$ uv run devops ci test tests/research/test_version_match.py tests/research/test_advisories.py`
- [x] 1.2 Implement comparator normalization and `patched_version` bounding in `src/devops_cli/research/version_match.py`, and pass `vulnerability.fixed_version` from `_github_matches` in `src/devops_cli/research/advisories.py`.
  - Verification: `$ uv run devops ci test tests/research/test_version_match.py tests/research/test_advisories.py`

Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

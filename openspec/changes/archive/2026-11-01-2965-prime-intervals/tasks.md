# Tasks

## 1. Set the prime intervals

Reads: none. Changes: `src/devops_cli/config/defaults.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/lang/en/help.py`, the documents and the tests that name an interval.

- [x] 1.1 Set the prime intervals in `src/devops_cli/config/defaults.py` and name them in the docstrings, the documents and the generated command documents
- [x] 1.2 Add `tests/roadmap/test_roadmap_intervals.py`, which fails when a default interval is not a prime or is a multiple of 5
- [x] 1.3 Verify that `uv run devops ci test tests/roadmap tests/server tests/k8s tests/docs` passes

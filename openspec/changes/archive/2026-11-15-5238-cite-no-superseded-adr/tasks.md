# Tasks

## 1. Fail on a citation of a superseded record

Reads: `src/devops_cli/roadmap/adr.py`, `docs/adr/`, `tests/support/paths.py`.

Changes: `tests/invariants/test_adr_superseded_citations.py`, the citation lines under `src/`, `tests/` and `.github/`.

- [x] 1.1 Write the test and watch it fail on the current citations.
  - Verification: `$ uv run devops ci test tests/invariants/test_adr_superseded_citations.py`
- [x] 1.2 Move the citations to the record in force.
  - Verification: `$ uv run devops ci test tests/invariants/test_adr_superseded_citations.py tests/roadmap`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

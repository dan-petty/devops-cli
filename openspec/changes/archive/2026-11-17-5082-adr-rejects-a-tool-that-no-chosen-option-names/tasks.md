# Tasks

## 1. Behavior

- [x] 1.1 Write the failing replay tests for the #4661 census and the mixed-marker option.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_adr.py`
- [x] 1.2 Invert the rejection rule around the chosen or adopted option.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_adr.py`

## 2. Documents

- [x] 2.1 Correct the rule in `docs/roadmap/alternatives.md`.
  - Verification: `$ uv run devops ci docs`
- [x] 2.2 Update the `roadmap-alternatives` specification.
  - Verification: `$ uv run devops openspec check`
- [x] 2.3 Archive the change into the main specification.
  - Verification: `$ uv run devops openspec archive 5082-adr-rejects-a-tool-that-no-chosen-option-names`

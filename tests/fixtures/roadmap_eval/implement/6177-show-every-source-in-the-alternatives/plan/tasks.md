# Tasks

## 1. Behavior

- [ ] 1.1 Change the sources test: a reply with eight sources shows all eight in the closed block and no "left out" line
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_alternatives.py`
- [ ] 1.2 Remove the bound, its constant, its row in the table of limits and its message
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_alternatives.py tests/roadmap/test_roadmap_limit_classes.py`

## 2. Documents

- [ ] 2.1 Update `docs/roadmap/alternatives.md` and the spec `roadmap-alternatives`
  - Verification: `$ uv run devops openspec check`

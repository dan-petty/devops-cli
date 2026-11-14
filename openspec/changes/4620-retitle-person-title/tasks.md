# Tasks

## 1. Keep a person's title across a body edit

Reads: `src/devops_cli/roadmap/retitle.py`. Changes: the same file, the spec delta, and `tests/roadmap/test_roadmap_retitle_type.py`.

- [ ] 1.1 Exclude the person-edit skip comment from the bound of the rename.
- [ ] 1.2 Add the spec delta for the two requirements.
- [ ] 1.3 Add the body-edit test.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_retitle_type.py` passes

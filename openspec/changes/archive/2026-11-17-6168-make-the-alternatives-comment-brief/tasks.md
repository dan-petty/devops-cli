# Tasks

## 1. Behavior

- [x] 1.1 Change the render tests to the new form: the folded block, the one tool line, the one-line skip class, and a long reply that the job writes whole
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_alternatives.py`
- [x] 1.2 Fold the evidence, write the tool on one line, make the footer and the skip-class comment short, and ask for a brief reply in the prompt
  - Verification: `$ uv run devops ci test tests/roadmap/`

## 2. Documents

- [x] 2.1 Update the comment form in `docs/roadmap/alternatives.md` and in the spec `roadmap-alternatives`
  - Verification: `$ uv run devops openspec check`

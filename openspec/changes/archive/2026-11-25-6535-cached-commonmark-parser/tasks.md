# Tasks

## 1. Behavior

- [x] 1.1 Add tests for cached CommonMark parser and source tree invariant
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_markdown.py`
- [x] 1.2 Implement `commonmark_parser()` in `src/devops_cli/roadmap/markdown.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_markdown.py`
- [x] 1.3 Update roadmap readers in `refine.py`, `stage_criteria.py`, and `step_files.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_markdown.py tests/roadmap/test_roadmap_refine.py`

## 2. Documents

- [x] 2.1 Add capability spec for roadmap-commonmark-parser
  - Verification: `$ uv run devops openspec check`

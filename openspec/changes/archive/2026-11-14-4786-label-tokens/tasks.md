# Tasks

## 1. Hold each color to its token

Reads: `src/devops_cli/roadmap/workflow_labels.py`. Changes: the same file and `tests/roadmap/test_roadmap_labels_file.py`.

- [x] 1.1 Add `LABEL_COLOR_TOKENS`.
- [x] 1.2 Extend the label color test with the token check.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_labels_file.py` passes

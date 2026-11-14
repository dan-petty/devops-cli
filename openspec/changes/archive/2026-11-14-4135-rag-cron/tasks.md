# Tasks

## 1. Check the scheduled ingest

Reads: `tests/commands/k8s/test_k8s_rag_ingest_manifests.py`. Changes: the same file.

- [x] 1.1 Add the render, select, schedule, template and args helpers.
- [x] 1.2 Add the five tests.
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s_rag_ingest_manifests.py` passes

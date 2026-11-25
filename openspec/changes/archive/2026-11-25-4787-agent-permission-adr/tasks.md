# Tasks

## 1. Record & Documentation

- [x] 1.1 Write `docs/adr/0038-owner-decisions-on-what-agents-may-do.md` with MADR 4 metadata, `body-hash`, and `### Decision 1` through `### Decision 5`, and update `k8s/README.md` Agent sessions text
  - Verification: `$ uv run pytest -n 0 tests/invariants/test_adr_records.py tests/docs/test_docs_inventory.py tests/docs/test_docs_knowledge_base_argv.py`
- [x] 1.2 Regenerate `docs/adr/README.md` and pass `devops docs check` and `devops openspec check`
  - Verification: `$ uv run devops docs generate && uv run devops docs check && uv run devops openspec check`

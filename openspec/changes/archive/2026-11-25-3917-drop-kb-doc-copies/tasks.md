# Tasks

## 1. Remove Copy Articles & Require Whole-KB Front Matter

- [x] 1.1 Write failing tests verifying the 4 copy articles and references are removed, `CONST_KB_METADATA_TARGET_SUBDIRS` equals all KB subfolders, and `kb_metadata_problems` rejects missing `applies_to` / covers all 71 articles
  - Verification: `$ uv run pytest -n 0 tests/review/test_kb_manuals_metadata.py tests/ai/test_kb.py tests/docs/test_docs_inventory.py`
- [x] 1.2 Delete the 4 copy articles, add valid YAML front matter to `src/devops_cli/ai/knowledge_base/devops_cli/tasks/*.md`, widen `CONST_KB_METADATA_TARGET_SUBDIRS`, add `kb_metadata_problems` in `src/devops_cli/ai/kb.py`, and update `src/devops_cli/ai/knowledge_base/README.md`
  - Verification: `$ uv run pytest -n 0 tests/review/test_kb_manuals_metadata.py tests/ai/test_kb.py tests/docs/test_docs_inventory.py`

## 2. Docs & Quality Gate

- [x] 2.1 Update `docs/SDLC.md`, regenerate `docs/KNOWLEDGE_BASE.md`, and verify `docs check`, `openspec check`, and `devops ci --check`
  - Verification: `$ uv run devops docs generate && uv run devops docs check && uv run devops openspec check && uv run devops ci --check`

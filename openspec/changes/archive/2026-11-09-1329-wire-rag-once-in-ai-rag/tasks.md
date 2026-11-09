# Tasks

## 1. Helper Exposure

- [x] 1.1 Expose repository ingest helpers in `src/devops_cli/ai/rag/ingest.py` as public functions.
  - Verification: `$ uv run ruff check src/devops_cli/ai/rag/ingest.py`

## 2. Test Refactoring

- [x] 2.1 Update `tests/ai/rag/test_rag_ingest.py` to use public helper names and drop private imports.
  - Verification: `$ uv run pytest tests/ai/rag/test_rag_ingest.py`
- [x] 2.2 Replace monkeypatch and mock instances in `tests/ai/rag/test_rag_ingest.py` with runner fixtures and fake objects.
  - Verification: `$ uv run pytest tests/ai/rag/test_rag_ingest.py`

## 3. Verification

- [x] 3.1 Run tests and verify zero private imports and zero internal patches in `tests/ai/rag/test_rag_ingest.py`.
  - Verification: `$ uv run pytest tests/ai/rag/test_rag_ingest.py`
- [x] 3.2 Run fast checks and gate checks.
  - Verification: `$ uv run devops ci`

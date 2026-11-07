# Tasks: Managed Repository RAG Ingestion

## 1. Visibility schema and payload filtering (behavior)

- [x] Write failing unit test for `visibility` keyword index and `must_not` filter in `SemanticRetriever`
  Verification: `uv run devops ci test tests/ai/rag/test_rag_retriever_filters.py`
- [x] Implement `visibility` keyword index in `CONST_RAG_PAYLOAD_INDEXES` and `must_not` unscoped search filter in `SemanticRetriever` and `qdrant.py`
  Verification: `uv run devops ci test tests/ai/rag/test_rag_retriever_filters.py`

## 2. Ingestion core module and repository pass (behavior)

- [x] Write failing test for repository ingestion logic in `tests/ai/rag/test_rag_ingest.py`
  Verification: `uv run devops ci test tests/ai/rag/test_rag_ingest.py`
- [x] Implement `src/devops_cli/ai/rag/ingest.py` with git runner, GitHub runner, visibility check, shallow checkout, and atomic state handling
  Verification: `uv run devops ci test tests/ai/rag/test_rag_ingest.py`

## 3. CLI command and metrics instrumentation (behavior)

- [x] Write failing test for `devops ai rag ingest` command and telemetry
  Verification: `uv run devops ci test tests/commands/test_rag.py`
- [x] Implement `devops ai rag ingest` in `src/devops_cli/commands/rag.py` and register `devops_cli_rag_ingest_runs_total` in `instruments.py`
  Verification: `uv run devops ci test tests/commands/test_rag.py`

## 4. Documentation and cheatsheet (documentation)

- [x] Create `docs/cheatsheets/ai_and_rag.md` and sync CLI reference
  Verification: `uv run devops docs generate --sync-readme && uv run devops docs check`

## 5. Verification and CI Gate (gate)

- [x] Run full CI checks
  Verification: `uv run devops ci`

## Workflow follow-up

- Argo cluster workflow lane for continuous multi-repo RAG indexing (#1389 follow-up).
- Pending a person: `uv run devops ai rag ingest` reports one first index per repository and exits 0.
- Pending a person: `devops ai rag status` shows the points.
- Pending a person: a second run straight after embeds nothing.
- Pending a person: after a push that edits, deletes and renames a file, a re-run makes `devops ai rag query "<text of the edit>" --project <owner>/<name>` return the new text.
- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).

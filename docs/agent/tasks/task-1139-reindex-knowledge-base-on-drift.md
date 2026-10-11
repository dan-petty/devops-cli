# Task: Re-index Knowledge Base on Drift & Qdrant Inspection (#1139)

**Issue**: [#1139](https://github.com/dan-petty/devops-cli/issues/1139)
**Status**: Done
**Milestone**: v0.2.34
**Priority**: priority/p1-high
**Scope**: scope/ai
**Feasibility**: Feasible - Confirmed offline through repository analysis that computing sha256 digests over sorted knowledge base markdown files and checking collection points during RAG entry points enables autonomous lazy re-indexing without LLM dependencies.

## Description
Ensures that the bundled DevOps CLI Knowledge Base stored in Qdrant is automatically kept synchronized with the installed package files. Whenever the knowledge base collection holds zero points or its recorded digest diverges from the installed knowledge base, RAG queries and chat lookups lazily trigger re-indexing before retrieving context. Additionally, `devops ai rag drift` and `devops ai rag status` inspect Qdrant store state directly instead of relying solely on the local filesystem cache.

Key components:
- **Collection records what it holds**: All points stored for the knowledge base (`project_name = "devops-cli-kb"`) record the sha256 digest over sorted relative file paths and contents, the active `embedding_model`, and `indexed_at` timestamp.
- **KB rebuilt on use**: On first RAG use in a process (chat context investigator, `devops ai rag query`, and MCP `rag_search` tool), checks point count and digest in Qdrant; if empty or differing from installed KB digest, triggers rebuild with a single progress line (`print_info("Rebuilding knowledge base index...", prefix=False)`). On failure, applies a 30-minute cooldown and warns once.
- **Drift reads Qdrant**: `devops ai rag drift` queries per-project point counts and knowledge base digests directly from Qdrant, detecting store-level drift even when the local cache file is intact.
- **Status displays store metadata**: `devops ai rag status` summarizes per-collection point count, embedding model, vector dimensions, knowledge base digest, and last index time.
- **Telemetry gauge**: Emits `devops_cli_rag_points` gauge on RAG use (#974).

## Acceptance Criteria
- [x] Knowledge base points in Qdrant carry installed KB digest (`sha256`), `embedding_model`, and `indexed_at` payload fields.
- [x] Knowledge base is rebuilt on first RAG use in a process (chat lookup, `rag query`, MCP RAG tools) when the collection holds no KB points or recorded digest differs.
- [x] Progress line `Rebuilding knowledge base index...` printed on re-index.
- [x] Rebuild failure enforces a 30-minute cooldown and warns at most once.
- [x] `devops ai rag drift` reads Qdrant per-project points and KB digest, reporting drift on wiped collections under intact caches.
- [x] `devops ai rag status` displays per collection: points, embedding model, dimension, KB digest, and last index time.
- [x] `devops_cli_rag_points` gauge is emitted on RAG use (#974).
- [x] Unit test suite in `tests/test_rag_kb_sync.py` runs completely offline with fakes under 1s each.
- [x] `changelog.d/1139.md` records the change under `### Fixed`.
- Pending a person: `uv run devops ci` on this branch; it is this PR's own check, which readiness reads.

## Measurements
The regression test suites, run offline with `uv run pytest`:

| Test Suite | Call Duration | Tests Passed |
| :--- | ---: | ---: |
| `tests/test_rag_kb_sync.py` | 0.95 s | 8 |
| `tests/test_architectural_invariants.py` | 14.93 s | 70 |
| `tests/test_agent_task_files.py` | 11.72 s | 510 |

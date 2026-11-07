# Change: Index managed repositories into RAG vector store (#1389)

## Why
Nothing ingests the managed repositories into the RAG vector index. A person must run `devops ai rag index` manually. Two of the eight managed repositories are private, and an unscoped search returns their chunks into search results that could be quoted in public contexts. Issue #1389 delivers `devops ai rag ingest`, which runs one pass over `service.repos`, records each point's visibility, and excludes private chunks from searches that do not name a project. The pass runs from a workstation with the operator's own git and GitHub credentials.

This change fits in one pull request.

## What Changes
- Adds `src/devops_cli/ai/rag/ingest.py` implementing repository ingestion logic (visibility inspection, shallow checkout, incremental workspace indexing, atomic state management, and cleanup of removed repositories).
- Adds the CLI command `devops ai rag ingest` (and `devops rag ingest`) supporting `--repo` narrowing, atomic failure isolation across repositories, and telemetry emission.
- Adds `visibility` payload field to indexed points and adds keyword payload index for `visibility` to `CONST_RAG_PAYLOAD_INDEXES`.
- Updates `SemanticRetriever` and Qdrant filtering to add a `must_not` condition on `visibility = private` when searching without an explicit project.
- Adds documentation in `docs/cheatsheets/ai_and_rag.md` and regenerates CLI reference.
- Adds comprehensive offline unit and integration tests under `tests/ai/rag/test_rag_ingest.py` and `tests/commands/test_rag.py`.

## Feasibility
Confirmed against the running system:
- Upstream `qdrant-client` 1.12+ supports `set_payload`, `create_payload_index`, `delete` by filter selector, and `Filter(must=..., must_not=...)`.
- Git CLI (version 2.43+) supports `ls-remote --symref <url> HEAD` for reading default branch and remote head commit, and shallow clone/fetch with `--depth 1`.
- Project settings `service.repos` (`ServiceConfig.repos`) and `data.rag_dir` exist and resolve safely through `safe_resolve_subpath`.

## Existing Tool Considered
No open, maintained tool covers the whole need. The alternatives check of 2026-11-01 returned `not-applicable` and named no tool, and the closest maintained pieces are the `git` CLI and `qdrant-client`: `git` supplies `ls-remote --symref` and the shallow clone/fetch (`git` docs), and `qdrant-client` supplies `set_payload`, `delete_points_by_project`, `count` and `create_payload_index` (https://qdrant.tech/documentation/tutorials-operations/incremental-embedding-updates/). Qdrant documents incremental re-embedding as a pipeline a caller writes, not as a library, so the project keeps a thin `src/devops_cli/ai/rag/ingest.py` and the `devops ai rag ingest` command on top of its existing `WorkspaceIndexer`. The written cost is about 250 to 400 lines of code and tests, about 40k tokens to build, about 10k tokens to keep and fix, and 1 to 2 engineer-days. Internal obsolete code deleted: none (extends existing RAG capabilities).

# Proposal

## Why
Commands under `ai analyze`, `ai ingest`, `ai rag`, and `ai research` make network, Valkey, Qdrant, or Kubernetes calls during execution or lack clear classification under the dry-run rule (#412, closes #2244).
Under `--dry-run`, commands that make external requests must execute zero requests and output an ordered `PlannedRequest` list, while local commands that make no external calls must run safely.

## What Changes
- Classify 21 AI commands across `ai analyze`, `ai ingest`, `ai rag`, and `ai research`:
  - 16 `request-plan` commands: `ai analyze branch`, `ai analyze path`, `ai analyze pr`, `ai ingest docs`, `ai ingest index-libraries`, `ai ingest query-library`, `ai rag clear`, `ai rag drift`, `ai rag index`, `ai rag index-kb`, `ai rag query`, `ai rag search`, `ai rag status`, `ai research analogies`, `ai research model`, and `ai research socratic`.
  - 5 `no-external-request` mark-only commands: `ai analyze`, `ai ingest library`, `ai rag`, `ai research annotate`, and `ai research forage`.
- Ensure all 16 `request-plan` commands make zero external requests (HTTP, Valkey, Qdrant, Kubernetes) when `--dry-run` or global `--dry-run` is active.
- Remove echo-only previews and remove all 21 commands from `tests/fixtures/dry_run_gaps.json`.
- Fits in one pull request.

## Capabilities

### Modified Capabilities
- `command-dry-run-class`: Add dry-run classification and request-plan specifications for AI analyze, ingest, rag, and research commands.

## Impact
- Affected files: `src/devops_cli/commands/analyze.py`, `src/devops_cli/commands/ai_ingest.py`, `src/devops_cli/commands/rag.py`, `src/devops_cli/commands/ai_research.py`, `src/devops_cli/ai/ai_plans.py`, and `tests/fixtures/dry_run_gaps.json`.
- Zero external breaking changes to public CLI flags.

## Feasibility
Confirmed against repository source:
- `analyze.py:254-520`: `analyze_branch`, `analyze_path`, and `analyze_pr` call `EmbeddingsEngine._query_ollama_node_batch` or git subprocesses.
- `ai_ingest.py:76-330`: `ingest_docs` calls `DocsIngester.ingest_remote_docs`; `index_libraries` and `query_library` access Valkey and Qdrant via `LibraryVectorStore`.
- `rag.py:30-450`: `rag_clear`, `rag_drift`, `rag_index`, `rag_index_kb`, `rag_query`, `rag_search`, and `rag_status` connect to Valkey and Qdrant.
- `ai_research.py:50-250`: `research_analogies` accesses Kubernetes cluster config, while `research_model` and `research_socratic` dispatch HTTP calls.
All 21 commands are present in `tests/fixtures/dry_run_gaps.json`.

## Existing Tool Considered
The implementation reuses the existing `devops_cli.dry_run.requests.PlannedRequest` and `render_request_plan` facilities. No third-party library is required. Rebuilding an external simulator is unnecessary.
Internal code deleted: echo-only previews in `rag.py` and `ai_research.py`.

# Design: Managed Repository RAG Ingestion

## Architecture Overview
The ingestion pass coordinates between git, GitHub metadata, and the local Qdrant vector database:
1. Validates preconditions (`qdrant.url` is configured, `service.repos` is not empty, all `--repo` options exist in `service.repos`).
2. Performs removed-repository cleanup by inspecting recorded state files under `data.rag_dir/repos/` and invoking `delete_points_by_project` for any project no longer in `service.repos`.
3. Sequentially processes each target repository:
   - Reads repository visibility via GitHub API (`run_gh` or session). If visibility changed from recorded state, updates existing points via `set_payload`.
   - Checks remote default branch and HEAD using `git ls-remote --symref <url> HEAD`.
   - If HEAD matches recorded state and `points_intact` returns true, skips re-indexing.
   - Otherwise, updates a shallow clone at `repos/<owner>/<name>/tree` via single-branch fetch and detached checkout.
   - Runs `WorkspaceIndexer.index_workspace` scoped to the repository tree, tagging every point with `visibility`.
   - Atomically writes `state.json` recording head, branch, visibility, and timestamp.
4. Error handling: Logs individual repository failures with traceback (except `ConfigurationError`) and continues with remaining repositories. Returns non-zero exit code if any repository failed.
5. Search filtering: In `SemanticRetriever`, any search without an explicit project adds a `must_not: {"visibility": "private"}` condition to ensure private chunks are excluded from unscoped queries.

## Rejected Alternatives
- **Service lane in roadmap-service**: Deferred by Owner Decision D11 to a separate Argo cluster lane. CLI command allows immediate workstation usage with user credentials and will be invoked by future cluster jobs.
- **Diff-based change detection with `git diff`**: Shallow clones lack commit history required for diffs against arbitrary prior commits. The existing content-hash cache in `WorkspaceIndexer` provides reliable change detection.
- **Separate collection for private repositories**: Multi-collection management introduces complexity across all RAG callers and review pipelines. A metadata filter (`visibility = private`) in `SemanticRetriever` cleanly handles scoping in a single shared schema.
- **Skipping private repositories**: Two of the managed repositories are private; excluding them would prevent RAG assistance for those projects.
- **Localhost fallback when `qdrant.url` is unset**: Issue #1165 and cluster network policies prohibit localhost fallbacks. An unset URL must fail immediately with `ConfigurationError`.

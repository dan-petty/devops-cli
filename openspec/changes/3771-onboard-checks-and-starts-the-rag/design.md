# Design

## Decisions

- **The three RAG rows live in a new `rag_rows` field of `OnboardingReport`, and `has_missing` and `not_readable_count` keep reading the seven prerequisite rows.**: The schedule fills the index with no step from a person, so a fresh repository would otherwise exit 1 for one poll interval, and the existing tests keep their answer.
- **The confirmed start calls `run_ingest_pass(repo_filter=[repo], settings=settings)` in the same process.**: The command already holds the repository name and the loaded settings, and a test doubles the pass at its seam instead of a subprocess.
- **The `indexed` row counts with `QdrantClient.count_points` and the payload filter `{"project_name": repo}`.**: Qdrant counts on the server, and the client moves one number instead of every point.
- **The `rag visibility` row compares the visibility of the points with the payload of the repository read that row 1 already makes.**: One read serves both rows, and a wrong value in the points shows as `mismatch` with both values.
- **The `rag schedule` row reads `service.repos` and reuses the step line of row 6.**: The scheduled pass of #1653 runs the ingestion with no `--repo`, so it covers exactly the repositories of that list.
- **`devops ai rag drift` gains `--repo owner/name` and keeps the directory name when the option is absent.**: `src/devops_cli/ai/rag/drift.py:305:class RAGDriftDetector:` names the project from the directory of the checkout, so the drift check of a worktree would read another project than the pass writes.
- **The `--dry-run` request plan keeps the label creation only.**: The dry run lists the GitHub requests of the command; the pass runs through the command of #1389, and the `rag schedule` row and the page name it.

## Rejected alternatives

- **Read the local index cache to decide the `indexed` row.**: `docs/adr/0005-review-findings-come-from-tools-not-models.md` records that drift against the local cache looked like no drift after both collections were wiped, so the row reads Qdrant.
- **Run the pass with no `--repo` narrowing.**: `run_ingest_pass` cleans up every configured repository (`src/devops_cli/ai/rag/ingest.py:381:cleanup_removed_repos(rag_dir, set(configured_repos), indexer)`), and the issue asks for one repository.
- **Name the project from the directory of the checkout.**: `src/devops_cli/ai/rag/drift.py:317:self.project = detect_project_name(self.root_dir, self.root_dir)` shows the directory name, and a worktree directory is not the repository name.
- **Fail the command on a `missing` or `mismatch` RAG row.**: A repository that waits one poll interval for its first pass would exit 1, and a script would read a fault.

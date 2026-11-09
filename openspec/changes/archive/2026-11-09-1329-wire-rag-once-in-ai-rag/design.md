# Design

## Decisions

- **Expose ingest helpers as public functions**: `resolve_repo_paths`, `read_repo_visibility`, `load_repo_state`, `cleanup_removed_repos` and `update_points_visibility` in `src/devops_cli/ai/rag/ingest.py` become public. Testing functions through public interfaces adheres to `docs/TESTING.md` and eliminates private imports.
- **Test repository errors through the git runner parameter**: Instead of patching `ingest_repository`, tests pass a custom `git_runner` that raises `GitOperationError`. `run_ingest_pass` catches the error and accumulates the failed repository as expected.
- **Verify telemetry using the OTLP fixture**: Instead of patching `emit`, tests verify that `RAG_INGEST_LAST_SUCCESS_TIMESTAMP` arrives in the `otlp` fake collector.
- **Use simple fake objects instead of MagicMock**: Subclassing `FakeQdrantClient` and using simple result objects removes mock libraries from the test suite.

## Rejected alternatives

- **Keep private function names and suppress warnings**: Rejected because Rule 1 and issue #1329 require zero private imports from `devops_cli`.
- **Monkeypatch `emit` or `ingest_repository`**: Rejected because `docs/TESTING.md` forbids patching `devops_cli` internals.

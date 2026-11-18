# Design

## Decisions

- **The three rows live in a new `rag_rows` field of the onboarding report, and `has_missing` and `not_readable_count` keep reading `rows`.**: The scheduled pass fills the index with no step from a person, so a fresh repository would exit 1 for one poll interval otherwise, and the existing tests keep their answer.
- **The confirmed start calls `run_ingest_pass(repo_filter=[repo], settings=settings)` in the same process.**: The command already holds the repository name and the loaded settings, the pass is the only writer to Qdrant, and a test doubles the pass at its seam instead of a subprocess.
- **The `indexed` row counts with `count_points` and the payload filter `{"project_name": repo}`.**: Qdrant counts on the server, so the client moves one number instead of every point, and the drift check already counts this way.
- **The visibility row compares the `visibility` of one point with the payload of the repository read that row 1 already makes, and reads `not indexed` with no point.**: One read serves both rows, the row sends no second request, and a wrong or absent value in the points shows as `mismatch` with both values.
- **The schedule row reads `settings.service.repos` and reuses the step line of row 6.**: The scheduled pass of #1653 runs the ingestion with no `--repo`, so it covers exactly the repositories of that list, and the command never writes `config.yaml`.
- **The drift check gets the project name in two steps: the `project` keyword of the detector first, then the `--repo` option of `drift_cmd` that passes it.**: Each step has a test in the module that exercises its own file, so the detector test and the command test both run in the group that writes them.
- **`devops ai rag drift` keeps the directory name when `--repo` is absent.**: The local `devops ai rag index` workflow of a checkout names the project from the directory, and the option is the way to name another project.
- **`plan_ai_rag_drift` keeps its signature and the dry-run branch of `drift_cmd` passes no project.**: The dry-run request list holds one scroll of the collection and no request that names the project, so a project argument would change no planned request.
- **The collection names come from one helper in `src/devops_cli/ai/rag/indexer.py` that `resolve_rag_components` also calls.**: `resolve_rag_components` builds an embedder that the rows do not need, and the naming rule stays in one place.
- **A `not readable` reason and a rendered row hold no Qdrant API key, and the test `test_onboard_rag_rows_print_no_qdrant_api_key` asserts it.**: The rows reach Qdrant with the configured key, and the command prints its rows to a terminal and to logs.

## Rejected alternatives

- **Read the local index cache to decide the indexed row.**: `docs/adr/0005-review-findings-come-from-tools-not-models.md` records that drift against the local cache looked like no drift after both collections were wiped, so the row reads Qdrant.
- **Run the pass with no repository narrowing.**: `src/devops_cli/ai/rag/ingest.py:381:` `cleanup_removed_repos(rag_dir, set(configured_repos), indexer)` runs over every configured repository, and the issue asks for one repository.
- **Name the project from the directory of the checkout.**: `src/devops_cli/ai/rag/drift.py:317:` `self.project = detect_project_name(self.root_dir, self.root_dir)` shows the directory name, and a worktree directory is not the repository name.
- **Keep the detector keyword and the command option in one group whose verify runs only the detector test.**: `tests/ai/rag/test_index_drift.py` imports neither `src/devops_cli/commands/rag.py` nor the option, so the option would be written with no test that runs it.
- **Fail the command on a missing or mismatch RAG row.**: A repository that waits one poll interval for its first pass would exit 1, and a script would read a fault.
- **Print the reason of a failed count with the endpoint and the key for diagnosis.**: `src/devops_cli/ai/rag/indexer.py` resolves the key with `get_qdrant_api_key`, and the row text goes to the terminal and the logs.

## Security

The `indexed` and `rag visibility` rows reach Qdrant with the API key that the settings resolve, so that key crosses from the local key store to the endpoint of `qdrant.url` on each count and scroll; the repository payload that the rows compare comes from the GitHub read of row 1 and stays local. A person must confirm that a `not readable` reason and a rendered row never hold the key or the endpoint, and that `--confirm` keeps the pass of #1389 as the only writer to Qdrant. The test `test_onboard_rag_rows_print_no_qdrant_api_key` in `tests/roadmap/test_roadmap_onboard.py` fails when the rendered report or a reason holds the configured key value.

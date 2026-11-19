# Proposal

## Why

The scheduled ingest runs `devops ai rag ingest`, which calls `run_ingest_pass` over `service.repos`, but no test asserts that one pass gives each configured repository at least one indexed point. An ingest that skips one repository leaves the index incomplete, and search returns nothing for that repository. This change adds the offline test that fails, naming the repository, when one has no point (#3949).

## What Changes

- Add `_run_collection`, `_indexed_repository_counts` and `_assert_repositories_indexed` to `tests/ai/rag/test_rag_ingest.py`, beside `_make_bare_remote`.
- Add `test_ingest_pass_indexes_each_managed_repository`, which runs one `run_ingest_pass` over three fixture remotes into a collection named for the run and asserts at least one point for each `project_name`.
- Delete the run-named collection in a `finally` and assert its name is absent from `list_collections()`, so the test leaves no collection behind.
- Add `test_coverage_assertion_names_the_repository_with_no_point`, which passes all three repositories and counts for two of them, and asserts that the message names the third.
- Add `test_ingest_pass_leaves_no_run_collection`, which runs the pass twice on the same fake client, each run with its own data directory and its own run-named collection, and asserts the same per-repository counts and no collection left.
- The change touches only `tests/ai/rag/test_rag_ingest.py`, so it carries no spec delta: it changes no behavior that a consumer observes.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Tests: `tests/ai/rag/test_rag_ingest.py`

## Feasibility

- The probes report, word for word: The path `tests/ai/rag/test_rag_ingest.py` is a file of the staging commit. The path `tests/support/fakes/qdrant.py` is a file of the staging commit.
- `read_file` of `tests/ai/rag/test_rag_ingest.py` lines 1-130 showed the fixture helper `tests/ai/rag/test_rag_ingest.py:55:def _make_bare_remote(bare_dir: Path, files: dict[str, str], branch: str = "main") -> Path:` and the module fixture `tests/ai/rag/test_rag_ingest.py:32:pytestmark = pytest.mark.usefixtures("keyring_store")`.
- `read_file` of `tests/ai/rag/test_rag_ingest.py` lines 180-300 showed the only per-repository counts in the module: `tests/ai/rag/test_rag_ingest.py:224:assert fake_qdrant.count_points("devops_code", {"project_name": "owner/removed-repo"}) == 0` and `tests/ai/rag/test_rag_ingest.py:228:assert fake_qdrant.count_points("devops_code", {"project_name": "owner/kept-repo"}) >= 1`, both in the cleanup test of one removed repository, so no test asserts coverage of every configured repository.
- `read_file` of `src/devops_cli/ai/rag/ingest.py` lines 250-420 showed the pass indexes each tree as its repository: `src/devops_cli/ai/rag/ingest.py:291:repo_indexer.index_workspace(` with `src/devops_cli/ai/rag/ingest.py:293:project=repo,`, and the indexer writes that key at `src/devops_cli/ai/rag/indexer.py:332:"project_name": chunk.project_name,`.
- `read_file` of `src/devops_cli/ai/rag/ingest.py` showed the pass takes the fixture remotes, its own data directory and an injected indexer: `src/devops_cli/ai/rag/ingest.py:365:remote_urls: dict[str, str] | None = None,`, `src/devops_cli/ai/rag/ingest.py:367:data_dir: Path | None = None,` and `src/devops_cli/ai/rag/ingest.py:370:indexer: WorkspaceIndexer | None = None,`, and the command calls it at `src/devops_cli/commands/rag.py:846:results = run_ingest_pass(`.
- `read_file` of `src/devops_cli/ai/rag/indexer.py` lines 690-735 answered the first review finding: the intact check reads the counts file that the first run wrote, `src/devops_cli/ai/rag/indexer.py:713:if project in counts:` and `src/devops_cli/ai/rag/indexer.py:716:prev_count = proj_counts.get(coll, 0)`, so a fresh collection holds no recorded count and the project counts as intact, and `src/devops_cli/ai/rag/ingest.py:278:if recorded_head == head and intact:` then skips the repository. The two-run test now gives each run its own `data_dir=` and its own indexer `cache_dir=`, so each run starts with no state and no counts, and indexes into its own run-named collection.
- The second review finding is answered by the signature of the helper: `_assert_repositories_indexed(repos, counts)` takes the three expected repositories as well as the counts, so it names a repository that is absent from the counts as well as one whose count is 0. The two-repository case passes all three repositories and counts for two, and the message names the third.
- `read_file` of `src/devops_cli/ai/rag/indexer.py` lines 636-670 showed the injected class and the collection it takes: `src/devops_cli/ai/rag/indexer.py:639:class WorkspaceIndexer:` and `src/devops_cli/ai/rag/indexer.py:647:code_collection: str = DEFAULT_RAG_COLLECTION,`.
- The constant the plan relies on is staged: `src/devops_cli/config/defaults.py:245:DEFAULT_RAG_COLLECTION = "devops_code"`, the collection that a scheduled run fills; the test replaces it with a collection named for the run.
- `read_file` of `tests/support/fakes/qdrant.py` lines 44-215 showed the fake supplies the store and the cleanup: `tests/support/fakes/qdrant.py:50:class FakeQdrantClient(QdrantProtocol):`, `tests/support/fakes/qdrant.py:132:def list_collections(self) -> list[str]:`, `tests/support/fakes/qdrant.py:138:def delete_collection(self, name: str) -> bool:` and `tests/support/fakes/qdrant.py:201:def count_points(self, name: str, filter_payload: dict[str, Any] | None = None) -> int:`.
- Precondition of `_make_bare_remote` (`tests/ai/rag/test_rag_ingest.py:55:def _make_bare_remote(`): a checkout of each fixture repository. It runs `git init`, `git commit`, `git remote add` and `git push` over `file://` paths, with `git` in the runner image and no network.
- Precondition of `run_ingest_pass` (`src/devops_cli/ai/rag/ingest.py:361:def run_ingest_pass(`): no client of a service and no network, because the test passes `indexer=`, `remote_urls=`, `gh_runner=` and `data_dir=`, and it sets `qdrant.url`, which the pass requires at `src/devops_cli/ai/rag/ingest.py:318:if not settings.qdrant.url:`.
- Precondition of the constructor of the injected indexer (`src/devops_cli/ai/rag/indexer.py:639:class WorkspaceIndexer:`): a client of the keyring, because it resolves the Qdrant API key when the given client holds none, at `src/devops_cli/ai/rag/indexer.py:661:self.qdrant.api_key = get_qdrant_api_key(load_settings())`; the `keyring_store` fixture supplies an isolated store.
- Precondition of `count_points`, `delete_collection` and `list_collections` of the fake (`tests/support/fakes/qdrant.py:50:class FakeQdrantClient(QdrantProtocol):`): no precondition. They read and change the in-memory store and reach no Qdrant server.
- The refine block says no manifest defines a scheduled RAG ingest, and the staged tree holds one: `k8s/devops/cronworkflow-rag-ingest.yaml:10:schedule: "*/3 * * * *"` runs `k8s/devops/workflowtemplate-rag-ingest.yaml:41:args: ["ai", "rag", "ingest"]`. The controller watches only namespace `argo-workflows` (`k8s/argo-workflows/values.yaml:26:singleNamespace: true`), so the schedule does not run yet; the test covers the pass that it runs and adds no manifest check.
- `uv run devops ci test tests/ai/rag/test_rag_ingest.py` needs `uv`, `pytest` and `git`, and all three are in the runner image. A failing assertion is failure class `test`, whose action is `repair`, and a run past its limit is `timeout`, whose action is `retry`. The pod sets `readOnlyRootFilesystem: true`, and the test writes only under pytest's `tmp_path`.
- The first checks the implementation runs: `uv run devops ci test tests/ai/rag/test_rag_ingest.py` fails before the new tests exist, then the same command passes, then `uv run devops ci --check --only lint`.
- `read_issue` of #1653 showed the issue closed (completed) and released in v0.94.0, so the CronWorkflow that runs the pass is already on the default branch and this item adds only the test.
- `find_issues` with `rag ingest coverage` listed open item #4566, which lets Argo Workflows run roadmap pods in namespace `devops`; this change touches no manifest and no schedule, so it waits on nothing.

## Existing Tool Considered

pytest runs the test and qdrant-client supplies the point count, but no library supplies a per-repository coverage assertion over `service.repos`. The change builds about 80 lines of test code in one module: about 20k tokens to build, about 5k tokens to keep and fix, and about 4 hours. It deletes no internal code.

## Dependencies

None.

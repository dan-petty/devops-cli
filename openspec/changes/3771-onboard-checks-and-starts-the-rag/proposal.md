# Proposal

## Why

Issue #3771: a person who adds a managed repository cannot tell whether Qdrant holds its code and documents, whether its points record the right visibility, or whether the scheduled pass covers it. The drift check also names the project after the directory, so a worktree reads another project than the pass writes.

## What Changes

- Add the `indexed`, `rag visibility` and `rag schedule` rows to `devops roadmap onboard`, in a `rag_rows` field that the exit code does not read.
- Count the points of the project in both collections with a `project_name` payload filter, and compare the visibility of one point with the repository payload that row 1 already reads.
- Print the line to add when `service.repos` leaves the repository out, and write no file.
- Start the ingestion pass for one repository with `--confirm` when `service.repos` holds it, and print the point count of each collection.
- Add the test that fails when a point of the pass carries the directory name instead of `owner/name`.
- Give the drift detector the project name of the repository, and give `devops ai rag drift` the option `--repo owner/name`, so the check reads the project that the pass writes.
- Describe the rows, the confirmed start and the exit-code rule in `docs/roadmap/onboard.md`.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `rag-drift`: Drift takes the project name of the repo option

### Modified Capabilities

- `roadmap-onboard`: The indexed row reads the points of the project, The indexed row reports an unreadable Qdrant, The visibility row compares the points with the repository read, The schedule row reads the repository list, The confirmed start runs the pass for one repository, A second confirmed start writes no point, The page describes the RAG rows, The exit code follows the missing rows
- `rag-ingest`: The pass names each project owner/name

## Impact

- Code: `src/devops_cli/roadmap/onboard.py`, `src/devops_cli/ai/rag/indexer.py`, `src/devops_cli/ai/rag/ingest.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/ai/rag/drift.py`, `src/devops_cli/commands/rag.py`, `src/devops_cli/lang/en/help.py`
- Documents: `docs/roadmap/onboard.md`, `docs/commands/roadmap.md`, `docs/commands/ai.md`
- Tests: `tests/roadmap/test_roadmap_onboard.py`, `tests/ai/rag/test_index_drift.py`, `tests/commands/test_ai_rag_ingest_analyze_dry_run.py`

## Feasibility

- The probe says: The path `docs/roadmap/onboard.md` is a file of the staging commit. The last criterion changes that page.
- The probe says: The path `src/devops_cli/ai/rag/indexer.py` is a file of the staging commit, and so is `src/devops_cli/ai/rag/drift.py`.
- The probe says: The path `config.yaml` is no file at the root of the staging commit. These files of the commit are candidates: `k8s/llm/gateway/config.yaml`, `openspec/config.yaml`. The schedule row therefore prints a line for a person, and the command writes no file.
- The probe says: The path `service.repos` is no file of the staging commit. It is a settings key, read at `src/devops_cli/roadmap/onboard.py:229:` `if repo in settings.service.repos:`.
- The check fault on the command citation is corrected. `read_file` on `src/devops_cli/commands/rag.py` lines 686-737 showed `src/devops_cli/commands/rag.py:686:` `def drift_cmd(` and its options, which hold no `--repo` at the staged commit, so the task text and the scenario now name `devops ai rag drift` and the option `--repo owner/name` in two code spans.
- The check fault on the class citation is corrected. `file_symbols` and `read_file` on `src/devops_cli/ai/rag/drift.py` showed `src/devops_cli/ai/rag/drift.py:305:` `class RAGDriftDetector:`, and the plan cites that line with its text instead of the symbol form.
- `read_file` on `src/devops_cli/commands/rag.py` lines 686-737 showed `src/devops_cli/commands/rag.py:731:` `detector = RAGDriftDetector(root_dir=path)`, the one call that the new option reaches, and `src/devops_cli/commands/rag.py:717:` `plan = plan_ai_rag_drift(`, so the dry-run plan keeps its signature.
- `search_code` with `HELP.rag.repo` showed `src/devops_cli/commands/rag.py:794:` `help=HELP.rag.repo,`, so the `--repo` option of the drift command reuses an existing help entry and the plan adds no language entry.
- `read_file` on `src/devops_cli/commands/roadmap.py` lines 1225-1300 showed `src/devops_cli/commands/roadmap.py:1252:` `repo: RepoOption = None,` and `src/devops_cli/commands/roadmap.py:1255:` `confirm: Annotated[bool, typer.Option("--confirm", help=HELP.roadmap.onboard_confirm)] = False,`, so the confirmed start joins a command that already takes the repository.
- `read_file` on `src/devops_cli/ai/rag/drift.py` lines 300-330 showed `src/devops_cli/ai/rag/drift.py:317:` `self.project = detect_project_name(self.root_dir, self.root_dir)`, the directory name that the new keyword replaces.
- `read_file` on `src/devops_cli/ai/rag/drift.py` lines 36-60 showed `src/devops_cli/ai/rag/drift.py:40:` `project: str`, so the report of the drift check names its project and a test can assert it.
- `read_file` on `src/devops_cli/ai/rag/drift.py` lines 200-236 showed `src/devops_cli/ai/rag/drift.py:200:` `def _count_collection_project_points(qdrant: Any, coll: str, project: str) -> int:` and `src/devops_cli/ai/rag/drift.py:204:` `cnt = qdrant.count_points(coll, filter_payload={"project_name": project})`, the count pattern that the indexed row reuses.
- `file_symbols` on `tests/ai/rag/test_index_drift.py` showed `tests/ai/rag/test_index_drift.py:27:` `def _detector(root: Path, indexer: WorkspaceIndexer) -> RAGDriftDetector:`, the helper that the test of group 3 sits beside.
- `read_file` on `tests/commands/test_ai_rag_ingest_analyze_dry_run.py` lines 30-45 showed `tests/commands/test_ai_rag_ingest_analyze_dry_run.py:38:` `drift_cmd as rag_drift_cmd,`, so the test of group 4 goes in the module that already runs the command.
- `file_symbols` on `src/devops_cli/roadmap/onboard.py` showed `src/devops_cli/roadmap/onboard.py:292:` `def check_onboarding(` and `src/devops_cli/roadmap/onboard.py:343:` `def render_onboarding(`, so the three rows join a report that exists.
- `read_file` on `src/devops_cli/roadmap/onboard.py` lines 51-380 showed `src/devops_cli/roadmap/onboard.py:73:` `return any(row.state == "missing" for row in self.rows)` and `src/devops_cli/roadmap/onboard.py:231:` `step = f"Add to service.repos in config.yaml:`, so the new rows need a field of their own and the step line of row 6 is reused.
- `read_file` on `src/devops_cli/ai/rag/ingest.py` lines 200-300 showed `src/devops_cli/ai/rag/ingest.py:293:` `project=repo,` and `src/devops_cli/ai/rag/ingest.py:278:` `if recorded_head == head and intact:`, so the pass already names each point `owner/name` and returns `skipped=True` for a current repository.
- `read_file` on `src/devops_cli/ai/rag/ingest.py` lines 70-96 showed `src/devops_cli/ai/rag/ingest.py:74:` `def read_repo_visibility(repo: str, gh_runner: Any) -> str:` and `src/devops_cli/ai/rag/ingest.py:83:` `raw_vis = str(data.get("visibility", "")).lower()`, the one copy of the visibility rule that the new row reuses.
- `read_file` on `src/devops_cli/ai/rag/ingest.py` lines 355-400 showed `src/devops_cli/ai/rag/ingest.py:361:` `def run_ingest_pass(` with `src/devops_cli/ai/rag/ingest.py:364:` `repo_filter: list[str] | None = None,`, so the confirmed start narrows the pass to one repository.
- `search_code` with `def count_points` showed `src/devops_cli/ai/rag/qdrant.py:813:` `def count_points(self, name: str, filter_payload: dict[str, Any] | None = None) -> int:` and `tests/support/fakes/qdrant.py:201:` `def count_points(self, name: str, filter_payload: dict[str, Any] | None = None) -> int:`, the client call and the fake seam.
- `read_file` on `tests/roadmap/test_roadmap_onboard.py` lines 1-40 showed `tests/roadmap/test_roadmap_onboard.py:24:` `REPO = "example/roadmap"`, so the row tests and the census test go in that module.
- `read_spec` for `roadmap-onboard` returned the requirement `The exit code follows the missing rows` with its scenario `One missing row`; `read_spec` for `rag-ingest` returned its 21 requirement names, so the delta modifies one requirement, adds one requirement to `rag-ingest` and opens no duplicate name.
- `read_issue` for #1389 showed `closed (completed)` with `Released in v0.77.0`; `read_issue` for #1653 showed `closed (completed)` with `Released in v0.94.0`, so both dependencies are delivered and neither blocks the plan.
- `run_ingest_pass` needs a network and a client of GitHub: it runs `git ls-remote --symref` and `gh api repos/<owner>/<name>` for each repository of the pass.
- `QdrantClient.count_points` needs a client of the Qdrant service, whose address comes from the setting `qdrant.url`.
- `RAGDriftDetector.detect_and_sync` needs a checkout of the repository, because it walks the working tree of the directory that it is given: `src/devops_cli/ai/rag/drift.py:373:` `def detect_and_sync(self, auto_sync: bool = False) -> RAGDriftReport:`.
- `check_onboarding` needs a client of GitHub and a roadmap store, because row 1 calls `session.rest` on the repository.
- The plan introduces two verify programs. `uv run devops ci test <module>` runs `pytest` from the runner image, with the failure class `test`. `uv run devops ci docs` runs the docs check of `devops` from the runner image, with the failure class `lint`. Both run in the runner pod with `readOnlyRootFilesystem: true`, `runAsNonRoot: true` and `capabilities.drop: ALL`. No program of the plan is `NOT_IN_RUNNER`.
- The plan makes one claim over every member of a set: each point that the pass writes carries the project name `owner/name`. No tool can count the points of a pass before it runs, so that count is unverified. The plan restricts every point to the project name of its repository and allowlists none. The census is `test_every_written_point_carries_the_repository_project_name` in `tests/roadmap/test_roadmap_onboard.py`, and the `verify` of group 1 runs that module, so the step stops when a point carries the directory name.

## Existing Tool Considered

Qdrant (https://github.com/qdrant/qdrant) with its Python client stores the points and counts them by payload filter. It has no onboard row, no comparison with the GitHub visibility and no schedule check, so the three rows, the confirmed start and the project name are project code on top of the pass of #1389: about 250k tokens and 2 hours to build, keep and fix. The change deletes no internal code.

## Dependencies

- #1389: it must be delivered first because the confirmed start runs the ingestion pass that this issue delivers, and the `indexed` row counts the points that the pass writes; `read_issue` shows it closed and released in v0.77.0.
- #1653: it must be delivered first because the `rag schedule` row reports whether its scheduled pass covers the repository; `read_issue` shows it closed and released in v0.94.0.

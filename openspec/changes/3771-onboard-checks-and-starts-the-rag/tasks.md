# Tasks

## 1. Add the RAG rows and the project name census

Kind: behavior. Reads: `src/devops_cli/roadmap/onboard.py`, `src/devops_cli/ai/rag/qdrant.py`, `src/devops_cli/ai/rag/indexer.py`, `src/devops_cli/ai/rag/ingest.py`, `tests/support/fakes/qdrant.py`, `tests/ai/rag/test_rag_ingest.py`, `tests/roadmap/test_roadmap_onboard.py`, `docs/roadmap/onboard.md`, `tests/commands/test_all_commands_help_dryrun.py`, `tests/ai/rag/test_codebase_hygiene_and_shims.py`, `tests/ai/rag/test_index_purge_and_recovery.py`, `tests/ai/rag/test_multi_project_indexing.py`, `tests/ai/rag/test_rag_qdrant.py`, `tests/ai/rag/test_workspace_indexing.py`, `tests/commands/test_rag.py`, `tests/ai/rag/test_embedding_model_compatibility.py`, `tests/ai/rag/test_index_drift.py`, `tests/ai/rag/test_indexing_failure_and_resume.py`, `tests/ai/rag/test_knowledge_base_sync.py`, `tests/ai/rag/test_qdrant_api_key_from_keyring.py`, `tests/ai/rag/test_qdrant_timeout_setting.py`, `tests/ai/rag/test_rag_component_wiring.py`, `tests/ai/test_kb.py`, `tests/infra/test_onboard.py`. Changes: `src/devops_cli/roadmap/onboard.py`, `src/devops_cli/ai/rag/indexer.py`, `src/devops_cli/ai/rag/ingest.py`, `tests/roadmap/test_roadmap_onboard.py`.
Adds: `check_rag_rows`, `rag_collection_names`, `visibility_from_payload`

- [x] 1.1 `test_onboard_rag_rows_read_the_index_the_visibility_and_the_schedule` and `test_onboard_rag_rows_print_no_qdrant_api_key` in `tests/roadmap/test_roadmap_onboard.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_onboard.py` fails on the base
- [x] 1.2 Write the failing tests first in `tests/roadmap/test_roadmap_onboard.py`, with the `qdrant` fixture of `tests/support/fakes/qdrant.py` and one seeded point of `example/roadmap`. Add `rag_collection_names(settings)` to `src/devops_cli/ai/rag/indexer.py` and let `resolve_rag_components` call it. Add `visibility_from_payload(data)` to `src/devops_cli/ai/rag/ingest.py` and let `read_repo_visibility` call it. Add `check_rag_rows(repo, settings, session, repo_payload)` to `src/devops_cli/roadmap/onboard.py`: it builds the client with `resolve_qdrant_client(settings=settings)`, counts with `count_points(coll, filter_payload={"project_name": repo})` in both collections, scrolls one point of the project for its `visibility` field, and returns the `indexed`, `rag visibility` and `rag schedule` rows. `_check_row_1` returns the repository payload beside its row, so the visibility row sends no second read. `OnboardingReport` gains the field `rag_rows`, and `has_missing` and `not_readable_count` keep reading `rows`, so the exit code stays on the seven prerequisite rows. `render_onboarding` prints the RAG rows after them. The second test sets a Qdrant API key in the settings, makes the count fail, and asserts that the rendered report and its reason hold no value of that key. Add the census test `test_every_written_point_carries_the_repository_project_name` to the same module: it runs `ingest_repository` for `example/roadmap` from a directory named `w-3566`, with the git and GitHub doubles of `tests/ai/rag/test_rag_ingest.py`, and asserts that each point of the fake Qdrant carries `example/roadmap` and that none carries `w-3566`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_onboard.py` passes

## 2. Start the pass from the confirmed onboarding

Kind: behavior. Reads: `src/devops_cli/roadmap/onboard.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/ai/rag/ingest.py`, `tests/roadmap/test_roadmap_onboard.py`, `tests/commands/test_all_commands_help_dryrun.py`, `tests/infra/test_onboard.py`, `tests/commands/test_roadmap_plan_check_cmd.py`, `tests/commands/test_roadmap_plan_recheck_cmd.py`, `tests/commands/test_roadmap_registries.py`, `tests/github/test_gh_issues_milestones_labels_runs_dry_run.py`, `tests/roadmap/implement/test_roadmap_implement_outside.py`, `tests/roadmap/test_roadmap_alternatives.py`, `tests/roadmap/test_roadmap_alternatives_item_writes.py`. Changes: `src/devops_cli/roadmap/onboard.py`, `src/devops_cli/commands/roadmap.py`, `tests/roadmap/test_roadmap_onboard.py`.
Adds: `start_rag_pass`

- [ ] 2.1 `test_onboard_confirm_starts_the_pass_for_one_repository` in `tests/roadmap/test_roadmap_onboard.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_onboard.py` fails on the base
- [ ] 2.2 Write the failing test first in `tests/roadmap/test_roadmap_onboard.py`: it doubles `devops_cli.ai.rag.ingest.run_ingest_pass`, runs `devops roadmap onboard --repo example/roadmap --confirm` with `service.repos` holding the repository, and asserts the call for that one repository and the printed point count of each collection. Add `start_rag_pass(repo, settings)` to `src/devops_cli/roadmap/onboard.py`, which imports and calls `run_ingest_pass(repo_filter=[repo], settings=settings)`. Call it from `onboard_cmd` in `src/devops_cli/commands/roadmap.py` after the label creation, when `--confirm` is given and `settings.service.repos` holds the repository, print the count of each collection, and print an error with no pass when the list leaves the repository out. The command counts and never upserts, deletes or sets a payload, so the pass is the only writer to Qdrant
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_onboard.py` passes

## 3. Give the drift detector the project name

Kind: behavior. Reads: `src/devops_cli/ai/rag/drift.py`, `src/devops_cli/commands/rag.py`, `tests/ai/rag/test_index_drift.py`, `tests/ai/rag/test_knowledge_base_sync.py`, `tests/commands/test_rag.py`. Changes: `src/devops_cli/ai/rag/drift.py`, `tests/ai/rag/test_index_drift.py`.

- [ ] 3.1 `test_drift_reads_the_project_name_of_the_repo_option` in `tests/ai/rag/test_index_drift.py`
  - Verification: `$ uv run devops ci test tests/ai/rag/test_index_drift.py` fails on the base
- [ ] 3.2 Write the failing test first in `tests/ai/rag/test_index_drift.py`, beside the helper at `tests/ai/rag/test_index_drift.py:27:` `def _detector(root: Path, indexer: WorkspaceIndexer) -> RAGDriftDetector:`. Give the detector at `src/devops_cli/ai/rag/drift.py:305:` `class RAGDriftDetector:` a `project` keyword, and set `self.project` to it when the caller gives one and to `detect_project_name(self.root_dir, self.root_dir)` otherwise. The test builds the detector over a directory named `w-3566` with `project="example/roadmap"` and asserts that the detector and its report name `example/roadmap` and never the directory name
  - Verification: `$ uv run devops ci test tests/ai/rag/test_index_drift.py` passes

## 4. Add the repo option to the drift command

Kind: behavior. Reads: `src/devops_cli/commands/rag.py`, `src/devops_cli/ai/rag/drift.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/ai/ai_plans.py`, `tests/commands/test_ai_rag_ingest_analyze_dry_run.py`, `tests/commands/test_all_commands_help_dryrun.py`, `tests/commands/test_rag.py`. Changes: `src/devops_cli/commands/rag.py`, `tests/commands/test_ai_rag_ingest_analyze_dry_run.py`.

- [ ] 4.1 `test_rag_drift_repo_option_names_the_project` in `tests/commands/test_ai_rag_ingest_analyze_dry_run.py`
  - Verification: `$ uv run devops ci test tests/commands/test_ai_rag_ingest_analyze_dry_run.py` fails on the base
- [ ] 4.2 Write the failing test first in `tests/commands/test_ai_rag_ingest_analyze_dry_run.py`, the module that imports the command at `tests/commands/test_ai_rag_ingest_analyze_dry_run.py:38:` `drift_cmd as rag_drift_cmd,`. It doubles `devops_cli.ai.rag.drift.RAGDriftDetector`, runs `devops ai rag drift` with the option `--repo example/roadmap`, and asserts that the detector was built with `project="example/roadmap"`. Add the option `--repo` to `drift_cmd` in `src/devops_cli/commands/rag.py` with the existing help entry `HELP.rag.repo`, and pass it to the detector at `src/devops_cli/commands/rag.py:731:` `detector = RAGDriftDetector(root_dir=path)` as `project=repo`. The dry-run branch keeps `plan_ai_rag_drift` unchanged, because its request list does not depend on the project name
  - Verification: `$ uv run devops ci test tests/commands/test_ai_rag_ingest_analyze_dry_run.py` passes

## 5. Document the RAG rows and the confirmed start

Kind: other. Reads: `docs/roadmap/onboard.md`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/commands/rag.py`, `tests/lang/test_language_catalogs.py`. Changes: `docs/roadmap/onboard.md`, `src/devops_cli/lang/en/help.py`, `docs/commands/roadmap.md`, `docs/commands/ai.md`.

- [ ] 5.1 Edit `docs/roadmap/onboard.md`: describe the `indexed`, `rag visibility` and `rag schedule` rows, the value of each, the `--confirm` start of the pass for one repository, and the exit-code rule that keeps the new rows out of it. Edit `HELP.roadmap.onboard_confirm` in `src/devops_cli/lang/en/help.py` to name the label creation and the start of the pass. Regenerate `docs/commands/roadmap.md` and `docs/commands/ai.md` with the docs generator and commit its output, so the `--repo` option of the drift command appears in the AI page
  - Verification: `$ uv run devops ci docs` passes
- [ ] 5.2 Edit `docs/roadmap/onboard.md` and `src/devops_cli/lang/en/help.py`, and regenerate `docs/commands/roadmap.md` and `docs/commands/ai.md` with the docs generator, and run `uv run devops docs generate`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: A row `indexed` reads `present` when both collections hold points of this repository (project `owner/name`), `missing` when they hold none, and `not readable` with the reason when Qdrant cannot be reached.
- Group 1: A row `rag visibility` reads whether the repository is recorded as private or public in its points, from `GET repos/<owner>/<name>`. An unscoped search leaves out a private repository (#1389), so a wrong value leaks or hides code.
- Group 1: A row `rag schedule` reads whether the scheduled pass of #1653 includes the repository (it reads the list that the pass uses, `service.repos`). When it does not, the command prints the line to add. It never edits `config.yaml`.
- Group 2: With `--confirm`, and only when the repository is in `service.repos`, the command runs the pass of #1389 for that one repository (`--repo owner/name`) and prints the number of points of each collection. It writes to Qdrant only through that pass.
- Group 1: The project name of every point written by the pass is `owner/name`. A test fails when it is the directory name.
- Group 2: A second run changes nothing when the repository is current (`devops ai rag drift` is clean).
- Group 5: `docs/roadmap/onboard.md` describes the rows.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

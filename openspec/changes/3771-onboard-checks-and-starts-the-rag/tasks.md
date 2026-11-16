# Tasks

## 1. Add the RAG rows to the onboarding report

Kind: behavior. Reads: `src/devops_cli/roadmap/onboard.py`, `src/devops_cli/ai/rag/qdrant.py`, `src/devops_cli/ai/rag/indexer.py`, `tests/support/fakes/qdrant.py`, `docs/roadmap/onboard.md`, `tests/commands/test_all_commands_help_dryrun.py`, `tests/infra/test_onboard.py`, `tests/lang/test_language_catalogs.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`, `tests/roadmap/refine/test_roadmap_refine_tracker.py`, `tests/roadmap/stage/test_roadmap_stage_module_test_order.py`, `tests/roadmap/stage/test_roadmap_stage_paths.py`, `tests/roadmap/stage/test_roadmap_stage_trace_subject.py`, `tests/roadmap/test_roadmap_onboard.py`. Changes: `src/devops_cli/roadmap/onboard.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_onboard.py`.
Adds: `rag_rows`, `_count_project_points`, `_point_visibility`

- [ ] 1.1 `test_onboard_rag_rows_read_the_index_the_visibility_and_the_schedule` in `tests/roadmap/test_roadmap_onboard.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_onboard.py` fails on the base
- [ ] 1.2 Write the failing test first in `tests/roadmap/test_roadmap_onboard.py`, with the `qdrant` fixture and seeded points. Add `rag_rows(repo, settings, repo_payload)` to `src/devops_cli/roadmap/onboard.py`: it builds the client with `resolve_qdrant_client(settings)`, names the collections `<prefix>_code` and `<prefix>_docs` from `settings.qdrant.collection_prefix`, counts with `count_points(coll, filter_payload={"project_name": repo})`, and returns the `indexed`, `rag visibility` and `rag schedule` rows. A count error or a missing `qdrant.url` gives the `indexed` row `not readable` with the reason. The `rag visibility` row reads one point with `scroll_points`, compares its `visibility` with the value of the repository payload that `_check_row_1` now returns, reads `mismatch` with `not recorded` when the points hold no value, and reads `not indexed` when the project holds no point. The `rag schedule` row reads `settings.service.repos` and reuses the row 6 step. `OnboardingReport` gains `rag_rows`, and `has_missing` and `not_readable_count` keep reading `rows`, so the exit code and the count stay on the seven prerequisite rows. `render_onboarding` prints the RAG rows after them. Put the row texts in `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_onboard.py` passes

## 2. Start the RAG pass from the confirmed onboarding

Kind: behavior. Reads: `src/devops_cli/roadmap/onboard.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/ai/rag/ingest.py`, `tests/ai/rag/test_rag_ingest.py`, `tests/commands/test_all_commands_help_dryrun.py`, `tests/commands/test_roadmap_plan_check_cmd.py`, `tests/commands/test_roadmap_plan_recheck_cmd.py`, `tests/commands/test_roadmap_registries.py`, `tests/github/test_gh_issues_milestones_labels_runs_dry_run.py`, `tests/infra/test_onboard.py`, `tests/lang/test_language_catalogs.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`, `tests/roadmap/implement/test_roadmap_implement_outside.py`, `tests/roadmap/refine/test_roadmap_refine_tracker.py`, `tests/roadmap/stage/test_roadmap_stage_module_test_order.py`, `tests/roadmap/stage/test_roadmap_stage_paths.py`, `tests/roadmap/stage/test_roadmap_stage_trace_subject.py`, `tests/roadmap/test_roadmap_alternatives.py`, `tests/roadmap/test_roadmap_alternatives_item_writes.py`, `tests/roadmap/test_roadmap_onboard.py`. Changes: `src/devops_cli/roadmap/onboard.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_onboard.py`.
Adds: `start_rag_pass`

- [ ] 2.1 `test_onboard_confirm_starts_the_pass_for_one_repository_and_names_the_project` in `tests/roadmap/test_roadmap_onboard.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_onboard.py` fails on the base
- [ ] 2.2 Write the failing test first. Add `start_rag_pass(repo, settings)` to `src/devops_cli/roadmap/onboard.py`: it imports `run_ingest_pass` from `devops_cli.ai.rag.ingest` inside the call and returns `run_ingest_pass(repo_filter=[repo], settings=settings)`. `onboard_cmd` in `src/devops_cli/commands/roadmap.py` calls it after the checks when `--confirm` is given and `service.repos` holds the repository, prints the point count of each collection with the counting helper, and prints an error with no pass when the list leaves the repository out. The pass is the only writer to Qdrant: the command counts and never upserts, deletes or sets a payload. A second run writes no point, because `ingest_repository` returns a skipped result when the recorded head equals the remote head and the points are intact. One test doubles `devops_cli.ai.rag.ingest.run_ingest_pass` and asserts the call for one repository; a second test runs the real pass from a directory named `w-3566` with the git, GitHub and indexer doubles of `tests/ai/rag/test_rag_ingest.py` and asserts that each written point carries the project name of the repository and that no point carries the directory name. Add the start texts to `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_onboard.py` passes

## 3. Name the project of the pass in the drift check

Kind: behavior. Reads: `src/devops_cli/ai/rag/drift.py`, `src/devops_cli/commands/rag.py`, `src/devops_cli/ai/ai_plans.py`, `tests/ai/rag/test_index_drift.py`, `tests/ai/rag/test_knowledge_base_sync.py`, `tests/commands/test_ai_rag_ingest_analyze_dry_run.py`, `tests/commands/test_rag.py`. Changes: `src/devops_cli/ai/rag/drift.py`, `src/devops_cli/commands/rag.py`, `src/devops_cli/ai/ai_plans.py`, `tests/ai/rag/test_index_drift.py`.

- [ ] 3.1 `test_drift_reads_the_project_name_of_the_repo_option` in `tests/ai/rag/test_index_drift.py`
  - Verification: `$ uv run devops ci test tests/ai/rag/test_index_drift.py` fails on the base
- [ ] 3.2 Write the failing test first in `tests/ai/rag/test_index_drift.py`. `RAGDriftDetector.__init__` in `src/devops_cli/ai/rag/drift.py` gains a `project` keyword: it uses the given name, and it falls back to `detect_project_name(self.root_dir, self.root_dir)` when the caller gives none. `drift_cmd` in `src/devops_cli/commands/rag.py` gains the option `--repo`, passes it to the detector, and passes it to `plan_ai_rag_drift` in `src/devops_cli/ai/ai_plans.py`, so the drift check of a worktree reads the points and the cache entries of the project that the option names
  - Verification: `$ uv run devops ci test tests/ai/rag/test_index_drift.py` passes

## 4. Document the RAG rows and the confirmed start

Kind: other. Reads: `docs/roadmap/onboard.md`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/commands/rag.py`, `tests/lang/test_language_catalogs.py`. Changes: `docs/roadmap/onboard.md`, `src/devops_cli/lang/en/help.py`, `docs/commands/roadmap.md`, `docs/commands/ai.md`.

- [ ] 4.1 Edit `docs/roadmap/onboard.md`: describe the `indexed`, `rag visibility` and `rag schedule` rows, each value, the `--confirm` start of the pass for one repository, and the exit-code rule that keeps the new rows out of it. Edit the `--confirm` help of `src/devops_cli/lang/en/help.py` to name the label creation and the start of the pass, and edit the help of the new `--repo` option of the drift command. Run `uv run devops docs generate` and commit `docs/commands/roadmap.md` and `docs/commands/ai.md` as its output
  - Verification: `$ uv run devops ci docs` passes
- [ ] 4.2 Edit `docs/roadmap/onboard.md`, edit the `--confirm` help of `src/devops_cli/lang/en/help.py`, and regenerate `docs/commands/roadmap.md` and `docs/commands/ai.md` with `uv run devops docs generate`, and run `uv run devops docs generate`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: A row `indexed` reads `present` when both collections hold points of this repository (project `owner/name`), `missing` when they hold none, and `not readable` with the reason when Qdrant cannot be reached.
- Group 1: A row `rag visibility` reads whether the repository is recorded as private or public in its points, from `GET repos/<owner>/<name>`. An unscoped search leaves out a private repository (#1389), so a wrong value leaks or hides code.
- Group 1: A row `rag schedule` reads whether the scheduled pass of #1653 includes the repository (it reads the list that the pass uses, `service.repos`). When it does not, the command prints the line to add. It never edits `config.yaml`.
- Group 2: With `--confirm`, and only when the repository is in `service.repos`, the command runs the pass of #1389 for that one repository (`--repo owner/name`) and prints the number of points of each collection. It writes to Qdrant only through that pass.
- Group 2: The project name of every point written by the pass is `owner/name`. A test fails when it is the directory name.
- Group 2: A second run changes nothing when the repository is current (`devops ai rag drift` is clean).
- Group 4: `docs/roadmap/onboard.md` describes the rows.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

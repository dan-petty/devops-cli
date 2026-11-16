# Proposal

## Why

Issue #3771: a person who adds a managed repository cannot tell whether Qdrant holds its code and documents, whether its points record the right visibility, or whether the scheduled pass covers it, and the pass names the project after the directory, so a worktree reads and writes the wrong project.

## What Changes

- Add the `indexed`, `rag visibility` and `rag schedule` rows to `devops roadmap onboard`.
- Count the points of the repository in both collections with a `project_name` payload filter, and read the visibility of the points with one scroll.
- Print the line to add when `service.repos` leaves the repository out, and never write `config.yaml`.
- Run the ingestion pass of #1389 for one repository with `--confirm` when `service.repos` holds it, and print the point count of each collection.
- Add `--repo owner/name` to `devops ai rag drift`, so the check reads the project of the pass and not the directory name.
- Keep the exit code on the seven prerequisite rows, so a repository that waits for its first poll exits 0.
- Describe the rows, the confirmed start and the exit-code rule in `docs/roadmap/onboard.md`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-onboard`: The indexed row reads the points of the repository, The indexed row reports an unreadable Qdrant, The visibility row compares the points with the repository read, The schedule row reads the repository list, The confirmed start runs the pass for one repository, A second confirmed start writes no point, The exit code follows the missing rows, The command is documented
- `rag-ingest`: The pass names each project owner/name, Drift compares the project that --repo names

## Impact

- Code: `src/devops_cli/roadmap/onboard.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/ai/rag/drift.py`, `src/devops_cli/commands/rag.py`, `src/devops_cli/ai/ai_plans.py`, `src/devops_cli/lang/en/help.py`
- Documents: `docs/roadmap/onboard.md`, `docs/commands/roadmap.md`, `docs/commands/ai.md`
- Tests: `tests/roadmap/test_roadmap_onboard.py`, `tests/ai/rag/test_index_drift.py`

## Feasibility

- The probe says: The path `docs/roadmap/onboard.md` is a file of the staging commit. That page is the one criterion 7 changes.
- The probe says: The path `src/devops_cli/ai/rag/indexer.py` is a file of the staging commit. It holds `resolve_qdrant_client`, which the rows use.
- The probe says: The path `src/devops_cli/ai/rag/drift.py` is a file of the staging commit. Group 3 changes it.
- The probe says: The path `config.yaml` is no file at the root of the staging commit. These files of the commit are candidates: `k8s/llm/gateway/config.yaml`, `openspec/config.yaml`. No commit in the history deleted or renamed it. So the schedule row prints a line for a person, and the command edits no file.
- The probe says: The path `service.repos` is no file of the staging commit. No commit in the history deleted or renamed it. `service.repos` is a settings key, read at `src/devops_cli/roadmap/onboard.py:229:if repo in settings.service.repos:`.
- `search_code` with `roadmap onboard` showed the living spec `openspec/specs/roadmap-onboard/spec.md`, the page `docs/roadmap/onboard.md` and the test module `tests/roadmap/test_roadmap_onboard.py`, so the command and its tests exist at the staging commit.
- `read_file` on `src/devops_cli/commands/roadmap.py` showed `def onboard_cmd(` at line 1251 with the `--plan`, `--dry-run` and `--confirm` options, so the plan extends a command that exists and keeps its one-mode-flag rule.
- `read_file` on `src/devops_cli/roadmap/onboard.py` showed `check_onboarding` building the seven rows and `render_onboarding` printing them, so the three rows join the report that the command prints.
- `read_file` on `src/devops_cli/commands/rag.py` showed `def ingest_cmd(` at line 788 with the option `"--repo",` at line 792, so the pass of #1389 already runs one repository.
- `read_file` on `src/devops_cli/ai/rag/ingest.py` showed `project=repo,` at line 293, so the pass already names each project `owner/name`; the plan adds the test that fails when the name is the directory name.
- `read_file` on `src/devops_cli/ai/rag/ingest.py` showed `if recorded_head == head and intact:` at line 278, so a second pass over a current repository writes no point.
- `read_file` on `src/devops_cli/ai/rag/drift.py` showed `self.project = detect_project_name(self.root_dir, self.root_dir)` at line 317, the directory name that the new option replaces.
- `search_code` for `def plan_ai_rag_drift` showed `src/devops_cli/ai/ai_plans.py:444:def plan_ai_rag_drift(`, the dry-run plan that group 3 gives the project name.
- `read_issue` for #1389 showed `closed (completed)` and `read_issue` for #1653 showed `closed (completed)`, and the archived changes `openspec/changes/archive/2026-11-07-1389-rag-ingest/` and `openspec/changes/archive/2026-11-14-4135-rag-cron/` hold their work, so neither dependency blocks the plan.
- `read_spec` for `roadmap-onboard` listed the requirement names, among them `The exit code follows the missing rows` and `The command is documented`, so the delta modifies those two names and adds no name that the capability already holds.
- `read_spec` for `rag-ingest` listed its purpose and its requirement names, among them `Default pass over service.repos` and `Visibility read and payload updates`, so the delta adds two new names there.
- `run_ingest_pass` needs a network: it runs `git ls-remote --symref` and `gh api repos/<owner>/<name>`, and it needs a client of the Qdrant service to write the points.
- `QdrantClient.count_points` and `QdrantClient.scroll_points` need a client of the Qdrant service, whose address comes from the setting `qdrant.url`.
- The method `rest` of `src/devops_cli/github/session.py:45:class GitHubSession:` needs a client of GitHub with the token of the job, and `acts_as_github_app` decides which identity the row 1 read uses.
- The method `detect_and_sync` of `src/devops_cli/ai/rag/drift.py:305:class RAGDriftDetector:` needs a checkout of the repository, because it walks the working tree of the directory it is given.
- The plan introduces two verify commands. `uv run devops ci test <module>` runs `pytest`, which the runner image holds, and its failure class is `test`. `uv run devops ci docs` runs the docs check from `devops`, which the runner image holds, and its failure class is `lint`. Both run under the pod settings `readOnlyRootFilesystem: true`, `runAsNonRoot: true` and `capabilities.drop: ALL`. No program of the plan is `NOT_IN_RUNNER`.
- The plan has one claim over every member of a set: each point the pass writes carries the project name `owner/name`. No tool can count those points before the run, so the count is unverified; the test `test_onboard_confirm_starts_the_pass_for_one_repository_and_names_the_project` asserts it over the points of one pass, and the `verify` of group 2 runs that test.
- The collection names come from `src/devops_cli/ai/rag/indexer.py:def resolve_rag_components`: `<prefix>_code` and `<prefix>_docs` from the setting `qdrant.collection_prefix`, whose fallback is the string `devops`.

## Existing Tool Considered

Qdrant (https://github.com/qdrant/qdrant) with its Python client stores the points and counts them by payload filter; the three rows, the repository comparison and the confirmed start are project code, about 250k tokens and 2 hours to build, keep and fix.

## Dependencies

- #1389: it must be delivered first because the confirmed start runs its pass, `devops ai rag ingest --repo owner/name`; it is closed and its change is archived at `openspec/changes/archive/2026-11-07-1389-rag-ingest/`.
- #1653: it must be delivered first because the `rag schedule` row reports whether its scheduled pass covers the repository; it is closed and its work is archived at `openspec/changes/archive/2026-11-14-4135-rag-cron/`.

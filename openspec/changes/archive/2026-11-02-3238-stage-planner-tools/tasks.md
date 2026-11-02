# Tasks

## 1. Read issues and search open items with the GitHub client

Kind: behavior. Reads: `src/devops_cli/github/client.py`, `tests/github/test_github_client.py`, `tests/support/fakes/github.py`. Changes: `src/devops_cli/github/client.py`, `tests/github/test_github_client_issue_reads.py` (new).

- [x] 1.1 Write `tests/github/test_github_client_issue_reads.py` for `get_issue`, `get_last_comments`, `get_closing_pull` and `search_open_items`, over the fake of the REST API
  - Verification: `uv run devops ci test tests/github/test_github_client_issue_reads.py` fails on the base
- [x] 1.2 Add the four read-only methods and their models to `GitHubClient`
  - Verification: `uv run devops ci test tests/github/test_github_client_issue_reads.py tests/github/test_github_client.py`

## 2. Add `read_issue` and `find_issues` to the planner

Kind: behavior. Reads: `src/devops_cli/security/sanitizer.py`, `src/devops_cli/roadmap/store.py`. Changes: `src/devops_cli/roadmap/stage_github.py` (new), `src/devops_cli/config/constants.py`, `tests/roadmap/test_roadmap_stage_github.py` (new), `tests/roadmap/test_roadmap_limit_classes.py`.

- [x] 2.1 Write `tests/roadmap/test_roadmap_stage_github.py` for the scenarios of "The tools read_issue and find_issues read GitHub and answer as text"
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_github.py` fails on the base
- [x] 2.2 Add `StageGitHub` with the masked, cut answers and the failure texts, add the limits as constants, and add them to the class table
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_github.py tests/roadmap/test_roadmap_limit_classes.py`

## 3. Add `references` and the toolset setting

Kind: behavior. Reads: `src/devops_cli/roadmap/stage_tools.py`, `src/devops_cli/roadmap/refine_investigation.py`, `src/devops_cli/config/settings.py`. Changes: `src/devops_cli/roadmap/stage_references.py` (new), `src/devops_cli/roadmap/stage_tools.py`, `src/devops_cli/roadmap/stage_toolbox.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/refine_investigation.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/config/settings.py`, `tests/roadmap/test_roadmap_stage_tools.py`, `tests/roadmap/test_roadmap_stage_toolbox.py`, `tests/roadmap/test_roadmap_stage_settings.py`, `tests/roadmap/test_roadmap_stage_plan.py`.

- [x] 3.1 Write the tests for the scenarios of "The setting toolset chooses the tools of a plan run", "The tool references counts a text in every file of the commit" and "The planner has a read-only toolbox", and change the test of the nine tools
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_tools.py tests/roadmap/test_roadmap_stage_toolbox.py tests/roadmap/test_roadmap_stage_settings.py tests/roadmap/test_roadmap_stage_plan.py` fails on the base
- [x] 3.2 Add the setting `roadmap.stage.toolset`, the tool `references`, the two tools that call `StageGitHub`, and the choice of the set in `StageTools.tools()` and `ToolboxClient`; give the job's `StageGitHub` to the planner
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_tools.py tests/roadmap/test_roadmap_stage_toolbox.py tests/roadmap/test_roadmap_stage_settings.py tests/roadmap/test_roadmap_stage_plan.py`

## 4. Say when to call the tools

Kind: behavior. Reads: `src/devops_cli/ai/tasks/roadmap_stage_tools.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_tools.md`, `src/devops_cli/ai/tasks/roadmap_stage_tools_extended.md` (new), `tests/roadmap/test_roadmap_stage_toolbox.py`.

- [x] 4.1 Write the tests that the prompt of each toolset names exactly the tools of the set, and verify that they fail on the base
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_toolbox.py` fails on the base
- [x] 4.2 Write `roadmap_stage_tools_extended.md` and take the network sentence out of `roadmap_stage_tools.md`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_toolbox.py tests/roadmap/test_roadmap_stage_prompt_rules.py`

## 5. Documents and the example ConfigMap

Kind: other. Reads: `docs/roadmap/stage.md`, `k8s/README.md`, `CONTEXT.md`. Changes: `docs/roadmap/stage.md`, `k8s/README.md`, `k8s/devops/configmap.example.yaml`, `CONTEXT.md`, `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`.

- [x] 5.1 Describe the toolset, the three tools and the GitHub read in `docs/roadmap/stage.md`, `k8s/README.md` and `CONTEXT.md`, set `toolset` in the example ConfigMap, and generate the documents again
  - Verification: `uv run devops docs generate --sync-readme` leaves no change, and `uv run devops ci docs` passes

## 6. Archive

Kind: other.

- [x] 6.1 Archive the change
  - Verification: `uv run devops openspec archive 3238-stage-planner-tools` and `uv run devops openspec check`

## Workflow follow-up

- Pending a person: confirm that the stage planner may read GitHub with the token of the Service (`roadmap.stage.toolset: extended`), or set `base`.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

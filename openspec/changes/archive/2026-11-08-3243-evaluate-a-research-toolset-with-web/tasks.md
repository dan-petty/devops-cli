# Tasks

## 1. Setting and Toolset Registry

Kind: behavior. Reads: `src/devops_cli/config/defaults.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/roadmap/tools.py`. Changes: `src/devops_cli/config/defaults.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/roadmap/tools.py`, `tests/roadmap/stage/test_roadmap_stage_settings.py`.

- [x] 1.1 Write tests for `toolset: research` and refusal of invalid toolsets naming `base`, `extended` and `research`
  - Verification: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_settings.py` fails on the base
- [x] 1.2 Add `research` to `StageToolset`, update settings validators, and register `HOLDER_STAGE_RESEARCH` in `tools.py`
  - Verification: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_settings.py`

## 2. Stage search_web tool and guardrails

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_tools.py`, `src/devops_cli/ai/web_search.py`, `src/devops_cli/security/sanitizer.py`. Changes: `src/devops_cli/roadmap/stage/stage_tools.py`, `src/devops_cli/config/constants.py`, `tests/roadmap/stage/test_roadmap_stage_tools.py`.

- [x] 2.1 Write failing tests for `StageTools.search_web`: 13 tools in research set, masking secrets, refusing internal hosts before provider call, cutting result snippets, and stopping at search limit
  - Verification: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_tools.py` fails on the base
- [x] 2.2 Implement `StageTools.search_web` with query guardrails, secret masking, search limit, and outcome metadata
  - Verification: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_tools.py`

## 3. Stage toolbox integration, prompt, and plan record

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_toolbox.py`, `src/devops_cli/roadmap/stage/stage_plan_record.py`. Changes: `src/devops_cli/roadmap/stage/stage_toolbox.py`, `src/devops_cli/roadmap/stage/stage_plan_record.py`, `src/devops_cli/ai/tasks/roadmap_stage_tools_research.md` (new), `tests/roadmap/stage/test_roadmap_stage_toolbox.py`, `tests/roadmap/stage/test_roadmap_stage_plan_record.py`.

- [x] 3.1 Write failing tests in `test_roadmap_stage_toolbox.py` and `test_roadmap_stage_plan_record.py` for research toolset offers, prompts, and prompt hash
  - Verification: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_toolbox.py tests/roadmap/stage/test_roadmap_stage_plan_record.py` fails on the base
- [x] 3.2 Update `ToolboxClient` to offer 13 tools and append `roadmap_stage_tools_research.md`, and update `prompt_version`
  - Verification: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_toolbox.py tests/roadmap/stage/test_roadmap_stage_plan_record.py`

## 4. Documentation and Spec Sync

Kind: documentation. Reads: `openspec/specs/roadmap-stage/spec.md`, `docs/ENV_VARS.md`, `docs/roadmap/stage.md`. Changes: `openspec/specs/roadmap-stage/spec.md`, `docs/ENV_VARS.md`, `docs/roadmap/stage.md`.

- [x] 4.1 Sync changes into `openspec/specs/roadmap-stage/spec.md` and update documentation
  - Verification: `uv run devops openspec check`

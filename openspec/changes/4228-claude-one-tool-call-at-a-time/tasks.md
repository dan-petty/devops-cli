# Tasks

## 1. A Claude group request forbids parallel tool calls

Kind: behavior. Reads: `src/devops_cli/ai/pydantic_ai_bridge.py`, `tests/ai/test_pydantic_ai_profiles_and_providers.py`. Changes: `src/devops_cli/ai/pydantic_ai_bridge.py`, `tests/ai/test_pydantic_ai_profiles_and_providers.py`.

- [x] 1.1 Add the tests: the request body to a Claude group holds `parallel_tool_calls` false, and a model that is not a Claude group sends none
  - Verification: `$ uv run devops ci test tests/ai/test_pydantic_ai_profiles_and_providers.py` fails on the base
- [x] 1.2 Add `parallel_tool_calls=False` to the `ModelSettings` of `_claude_group_model`
  - Verification: `$ uv run devops ci test tests/ai/test_pydantic_ai_profiles_and_providers.py` passes

## 2. A stop by invalid arguments names the cause

Kind: behavior. Reads: `src/devops_cli/roadmap/refine/refine_investigation.py`, `src/devops_cli/roadmap/stage/stage_toolbox.py`, `src/devops_cli/roadmap/stage/stage.py`. Changes: `src/devops_cli/roadmap/refine/refine_investigation.py`, `src/devops_cli/roadmap/stage/stage_toolbox.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/refine/test_roadmap_refine_investigation.py`, `tests/roadmap/stage/test_roadmap_stage_toolbox.py`.

- [x] 2.1 Add the tests: `investigate` with a last reply whose tool call holds joined JSON returns `InvestigationStopped` with `invalid_arguments` true and `schema_broken` false, for the output tool and for a function tool; a broken schema with valid JSON and a spent budget leave `invalid_arguments` false; the plan run and the review run of `ToolboxClient` raise a `RoadmapStageError` that names the invalid arguments and holds no "schema violation"
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_investigation.py tests/roadmap/stage/test_roadmap_stage_toolbox.py` fails on the base
- [x] 2.2 Add `invalid_arguments` to `InvestigationStopped`, set it in `_stopped_outcome` from the arguments of the tool calls of the last model reply, add the message to `MESSAGES.roadmap`, and raise it from `_stopped` in `stage_toolbox.py`
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_investigation.py tests/roadmap/stage/test_roadmap_stage_toolbox.py tests/roadmap/stage/test_roadmap_stage_plan.py` passes

## 3. Documents

Kind: documents. Changes: the documents that the change makes wrong, if any.

- [ ] 3.1 Search the documents for the old text of the stop ("0 schema violation(s)") and for the parallel tool calls of a Claude group, and fix each one that the change makes wrong
  - Verification: `$ uv run devops ci docs` passes
- [ ] 3.2 Validate the change folder
  - Verification: `$ uv run devops openspec check` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
- Pending a person: decide on a bump of the pinned LiteLLM image `v1.103.0` (the latest release on PyPI at the time of the plan is 1.108.3; v1.105.0 repairs the parse of joined arguments).

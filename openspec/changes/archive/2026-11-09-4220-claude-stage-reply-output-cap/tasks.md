# Tasks

## 1. A Claude group request carries the output cap

Kind: behavior. Reads: `src/devops_cli/ai/pydantic_ai_bridge.py`, `tests/ai/test_pydantic_ai_profiles_and_providers.py`. Changes: `src/devops_cli/ai/pydantic_ai_bridge.py`, `src/devops_cli/config/constants.py`, `tests/ai/test_pydantic_ai_profiles_and_providers.py`.

- [x] 1.1 Add the tests: the model of a Claude group has `settings["max_tokens"]` above 4096, the request body that reaches the gateway holds the cap, and a model that is not a Claude group sends none
  - Verification: `$ uv run devops ci test tests/ai/test_pydantic_ai_profiles_and_providers.py` fails on the base
- [x] 1.2 Pass `settings=ModelSettings(max_tokens=CONST_AI_CLAUDE_GROUP_MAX_OUTPUT_TOKENS)` to `OpenAIChatModel` in `_claude_group_model`
  - Verification: `$ uv run devops ci test tests/ai/test_pydantic_ai_profiles_and_providers.py` passes

## 2. A length stop names the output token limit

Kind: behavior. Reads: `src/devops_cli/roadmap/refine/refine_investigation.py`, `src/devops_cli/roadmap/stage/stage_toolbox.py`, `src/devops_cli/roadmap/stage/stage.py`. Changes: `src/devops_cli/roadmap/refine/refine_investigation.py`, `src/devops_cli/roadmap/stage/stage_toolbox.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/refine/test_roadmap_refine_investigation.py`, `tests/roadmap/stage/test_roadmap_stage_toolbox.py`, `tests/support/length_stop.py`.

- [x] 2.1 Add the tests: `investigate` with a model that answers `finish_reason` `length` with no part returns `InvestigationStopped` with `output_limit` true and `schema_broken` false; a broken schema and a spent budget leave `output_limit` false; the plan run and the review run of `ToolboxClient` raise a `RoadmapStageError` that names the output token limit and `max_tokens` and holds no "schema violation"
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_investigation.py tests/roadmap/stage/test_roadmap_stage_toolbox.py` fails on the base
- [x] 2.2 Add `output_limit` to `InvestigationStopped`, set it in `_stopped_outcome` from the finish reason of the last model reply, add the message to `MESSAGES.roadmap`, and raise it from `_stopped` in `stage_toolbox.py`
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_investigation.py tests/roadmap/stage/test_roadmap_stage_toolbox.py tests/roadmap/stage/test_roadmap_stage_plan.py` passes

## 3. Documents

Kind: documents. Changes: the documents that the change makes wrong, if any.

- [x] 3.1 Search the documents for the old text of the stop ("0 schema violation(s)", the default output limit of a Claude group) and fix each one that the change makes wrong
  - Verification: `$ uv run devops ci docs` passes
- [x] 3.2 Validate the change folder
  - Verification: `$ uv run devops openspec check` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
- Issue #4221 holds the second fault of the same live run: the window estimate drops the function tools too early. This change does not fix it.

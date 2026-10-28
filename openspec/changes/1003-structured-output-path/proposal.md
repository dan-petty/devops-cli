# Proposal

## Why

Issue #1003: three in-house paths parsed a model reply, validated it against a schema, sent the errors back to the model and asked again. The issue asked for one path.

On `origin/main` 4226904e, only one of the three runs in production:

- `chat_structured` (`ai/client/structured.py`) runs for roadmap intake, refine and research. It sends the schema in the system message, sets the wire constraint on the gateway and ollama providers, repairs the JSON, validates it, and retries with a schema reflection. It writes and serves only a reply that validates.
- The schema arm of the agent loop has no production caller. No module in `src` gives a `PydanticAgent` an `output_type`, an `output_schema` or an `output_validator`. The two agents that `devops ai` builds have none, and the review builds no agent since the evidence-first redesign (#1137).
- The pipeline's second parse has no production caller. The one production `MultiAgentPipeline` sets no `output_schema`, so `_parse_pipeline_output` returned None on every production run.
- `chat_structured` built its reflection message with its own copy of `build_schema_reflection_message`.

The owner's decision on #1001 is that structured output uses pydantic-ai's output modes (#1419). #1005 asks whether to adopt the native `pydantic_ai.Agent`, whose `output_type` validates and retries natively. A new hand-written module that both loops call would be one more layer to delete then. So this change makes `chat_structured` the one path by deleting the other two.

## What Changes

- `PydanticAgent` loses `output_type`, `output_schema`, the `output_type` and `output_json_schema` properties, the `output_validator` decorator, the schema block of its system prompt and its output validation stage. `AgentRetries` keeps only `tools`. `AgentSpec` and `AgentInfo` lose `output_schema`.
- `ai/agents/runner.py` loses `_validate_agent_output`, `_handle_schema_validation_retry` and `is_structured_output_schema`.
- `fix_llm_response` loses its `schema` argument and its validation helpers. `FormattedLLMResponse` loses `parsed_model`, `validation_error`, `schema_reflection` and `repair_notes`, and it is no longer generic. `parse_review_response` loses its branch that read `parsed_model`, which no reply reached: a reply that validated as `ReviewResult` always parsed to a dictionary first.
- `MultiAgentPipeline` loses `output_schema`, `_parse_pipeline_output`, `MultiAgentPipelineResult.final_data`, `PipelineStepResult.parsed_data` and its type parameter.
- `ai/output/` is deleted. Only the deleted arms used it.
- `chat_structured` uses `build_schema_reflection_message` from `ai/schema_reflection.py`, and its own copy is deleted. The message text does not change.
- A new invariant test, `tests/invariants/test_source_tree.py`, fails when a module other than `ai/client/structured.py` and `ai/schema_reflection.py` builds a schema reflection.
- No command, option, message or output changes, so the change has no spec delta.
- The change fits one pull request.

## Impact

- `src/devops_cli/ai/agents/{agent,context,pipeline,runner,testing,tools}.py`, `src/devops_cli/ai/client/structured.py`, `src/devops_cli/ai/response_repair.py`, `src/devops_cli/ai/review_schema.py`, `src/devops_cli/commands/ai.py`, and `src/devops_cli/ai/output/` (deleted).
- The knowledge-base page `ai/knowledge_base/devops_cli/libraries/pydantic_ai.md`.
- Tests: the new invariant; `tests/test_pydantic_ai_output.py` (deleted); the tests of the deleted arms in `test_pydantic_agent.py`, `test_schema_reflection.py`, `test_ai_fixer.py`, `test_ai_client_structured.py` and `test_batch_2_review_defects.py`; the pipeline tests that named the type parameter; `tests/fixtures/swallowed_failures_ceilings.json`, whose ceilings fall by 9.

## Feasibility

- `rg -n "output_type=|output_schema=|output_validator\(" src` on 4226904e found no caller outside `ai/agents/`. `rg -n "PydanticAgent\(" src` found two constructions, `commands/ai.py:1103` and `:1292`, and neither passes a schema. `rg -n "MultiAgentPipeline\(" src` found one, `commands/ai.py:1284`, with no `output_schema`.
- `rg -n "\.chat_structured\(" src` found the five production calls: `roadmap/refine.py:477` and `:1115`, `roadmap/intake_model.py:235`, `ai/research/mental_model.py:228` and `ai/research/socratic.py:147`.
- The new invariant failed on 4226904e: `ai/agents/runner.py` and `ai/response_repair.py` built schema reflections.
- The issue's open questions are decided on #1003 (comment of 2026-10-28): `chat_structured`'s policy survives; repair counting stays where #875 put it, and `devops_cli_ai_structured_attempts_total` already counts each attempt by outcome; the `profile.json` criterion is dropped, because the review makes no structured-output call; #1419 is independent and needs nothing from this change.

## Existing Tool Considered

pydantic-ai's `Agent` with `output_type` validates a reply and retries with the validation error, which covers the agent loop's arm. Production runs no native agent, and adopting one is #1005's question, so this change builds no bridge to it and deletes the hand-written arm instead. `chat_structured` keeps using pydantic for validation and `json-repair` for repair (#875). The change deletes 479 lines of source and builds nothing.

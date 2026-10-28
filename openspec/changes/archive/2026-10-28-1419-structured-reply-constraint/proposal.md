# Proposal

## Why

Issue #1419: `chat_structured` sends the reply's JSON Schema in the system message to every provider, but only the `gateway` and `ollama` providers also get it as a constraint on the reply. The `claude`, `openai` and `copilot` providers are prompt-only. Their replies can drift from the schema and cost a reflection retry, or fail the item after the last retry. `chat_structured` serves intake, refine and two research calls.

## What Changes

- The `openai` provider sends the `response_format` that pydantic-ai's `NativeOutput` sends for its model. `openai_model_profile` gives the model's profile. Its `OpenAIJsonSchemaTransformer` adapts the schema, and `strict` is true only when the schema fits OpenAI's strict mode (`is_strict_compatible`). The four schemas that `chat_structured` gets today do not fit it, so they go with `strict: false`.
- The `claude` provider sends `output_config.format` (`type: json_schema`) when `anthropic_model_profile` says that the model supports JSON-schema output. `AnthropicJsonSchemaTransformer` adapts the schema with the Anthropic SDK's `transform_schema`. A model that the profile does not name gets no format. The format goes beside the `effort` of adaptive thinking in the same `output_config`.
- The `copilot` provider sends no constraint. No profile or probe shows that the Copilot API honours one, so the schema stays in the system message only.
- The `gateway` and `ollama` providers send what they send today.
- A call outside `constrain_reply` sends no constraint, as before.
- `ReplySchema` (`ai/client/network.py`) owns the two provider forms, so the request builders of the OpenAI-compatible and Claude adapters read them from one place.
- The request body that a provider gets is observable, so the change carries a spec delta: the new capability `ai-structured-reply-constraint`.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `ai-structured-reply-constraint`: which constraint each provider gets for a structured reply, and in which form.

## Impact

- `src/devops_cli/ai/client/network.py`, `src/devops_cli/ai/client/openai.py`, `src/devops_cli/ai/client/claude.py`, and the docstring of `chat_structured` in `src/devops_cli/ai/client/structured.py`.
- `tests/test_ai_client_structured.py`.
- The knowledge-base page `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pydantic_ai.md`, which lists the constraint of each provider.

## Feasibility

- On `origin/main` 2d38f8d8, `_prepare_params` in `ai/client/openai.py` set `response_format` only for the `gateway` provider, and `_build_anthropic_kwargs` in `ai/client/claude.py` set no format. The new request-body tests failed on that code for `openai` and for the two `claude` cases with a supported model.
- The pinned libraries have every part (read in the installed packages):
  - pydantic-ai 2.54.0: `openai_model_profile` returns `supports_json_schema_output=True` and `json_schema_transformer=OpenAIJsonSchemaTransformer`. `anthropic_model_profile` sets `supports_json_schema_output` by model prefix (`claude-sonnet-4-5`, `claude-sonnet-4-6`, `claude-opus-4-1` and later, `claude-haiku-4-5` and later). pydantic-ai's own models build the native output this way: `Model.customize_request_parameters` walks the profile's transformer with the output's `strict` and sends `strict=is_strict_compatible` (`_customize_output_object`), `OpenAIChatModel._map_json_schema` sends `{"type": "json_schema", "json_schema": {"name", "schema", "strict"}}`, and `AnthropicModel` forces `strict=True` and sends `output_config={"format": {"type": "json_schema", "schema": ...}}` (`_build_output_config`).
  - anthropic 1.12.1: `messages.create` takes `output_config: OutputConfigParam`, whose `format` is a `JSONOutputFormatParam`. `anthropic.transform_schema` is a public export.
  - openai 3.26.1: `chat.completions.create` takes `response_format` with `stream=True`. The stream is read with `ChatCompletionStreamState` as before (#2365).
- The Claude documentation (platform.claude.com, "Structured outputs", read 2026-10-28) gives the request as `output_config.format`, says that structured outputs work with streaming, and that the grammar applies only to Claude's direct output and not to thinking. It lists citations and message prefilling as incompatible: `chat_structured` uses neither, and its retry ends the messages with a user turn. It limits a request to 24 optional parameters and 16 parameters with union types, and refuses a larger schema with a 400 error. After the Anthropic transform, the largest schema that `chat_structured` gets today has 13 optional parameters and 3 unions (`ModelProposal` of intake).
- The four schema names (`ModelProposal`, `RefinementProposal`, `MentalModel`, `SocraticInquiryResult`) match OpenAI's name rule `^[a-zA-Z0-9_-]{1,64}$`.
- #595's probes measure the gateway's deployments only, so they say nothing about the Copilot API. The owner decision on #1001 (2026-10-08, comment on #1419) chose pydantic-ai's output modes as each provider's profile supports them. #1001 then built the model seam as `LLMClient` over the official SDKs, so the change sends the request body that pydantic-ai's `NativeOutput` sends, through those SDKs.

## Existing Tool Considered

pydantic-ai's model profiles decide which model gets a constraint, and its schema transformers (`OpenAIJsonSchemaTransformer`, and `AnthropicJsonSchemaTransformer` over the Anthropic SDK's `transform_schema`) adapt the schema. The OpenAI and Anthropic SDKs carry the parameters. The change writes no schema rewriting and no capability table of its own, and it deletes the gateway-only branch of `_prepare_params`.

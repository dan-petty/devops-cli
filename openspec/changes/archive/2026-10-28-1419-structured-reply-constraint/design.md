# Design

## Context

`chat_structured` (`ai/client/structured.py`) sets the reply schema with `constrain_reply` for the calls of one structured reply. The request builder of each adapter reads it from the context variable `reply_schema`. The `gateway` and `ollama` adapters already turn it into their constraint. This change adds the `openai` and `claude` forms and records the `copilot` decision.

## Decisions

### The profile of the model decides, and the form is pydantic-ai's `NativeOutput` form

`ReplySchema.openai_response_format(model)` and `ReplySchema.anthropic_output_format(model)` read the pydantic-ai profile of the model and return the body part that pydantic-ai's `NativeOutput` sends, or None when the profile has no JSON-schema output. The OpenAI form walks the profile's transformer with `strict=None` and sends `strict` as `is_strict_compatible`, as `_customize_output_object` does. The Anthropic form walks `AnthropicJsonSchemaTransformer` with `strict=True`, as `AnthropicModel.prepare_request` forces for native output.

### `chat_structured` keeps its validation and its reflection retry

The constraint makes a valid first reply more likely. The reply is still repaired and validated against the Pydantic model, and a reply that fails gets the reflection retry. The OpenAI form is not strict for the current schemas, and the Anthropic transform moves the constraints that the API does not compile (for example `ge` and `le`) into descriptions, so the validation stays the check.

### Copilot stays prompt-only

The Copilot API serves models of several vendors behind one OpenAI-compatible endpoint. No pydantic-ai profile describes it, and no probe of this repository reaches it. A request with an unsupported `response_format` could fail with a 400 error where today it succeeds, so the provider keeps the schema in the system message only. The test asserts that its request has no `response_format`.

### A Claude model that the profile does not name gets no format

`anthropic_model_profile` names the models that support JSON-schema output. A model that it does not name, for example a model released after pydantic-ai 2.54.0, stays prompt-only until the pin moves. This is pydantic-ai's own default for such a model (`_default_structured_output_mode` returns `prompted`).

## Rejected alternatives

- **Run `chat_structured` on pydantic-ai's `Agent` with `NativeOutput`.** pydantic-ai would then send the constraint itself. Rejected: `chat_structured` runs on `LLMClient`, the model seam that #1001 built over the official SDKs, with its response cache, spend records, gateway slots and reflection retry. An `Agent` run would bypass each of them. #2489 owns the move of the agent runtime onto pydantic-ai's `Agent` and does not include `chat_structured`.
- **`ToolOutput` (a forced tool call) for Claude.** Rejected: the profile of each model that supports a forced output tool also supports JSON-schema output, and pydantic-ai uses native output for those models. A forced tool call also disables thinking on Opus 5 and Sonnet 4.6 and later (`forced_tool_choice_disables_thinking`).
- **The SDKs' own parse helpers** (`client.chat.completions.parse(response_format=Model)` and `messages.parse(output_format=Model)`). Rejected: they take the Pydantic class and return a parsed object, while `chat_structured` gets the reply as text through the streamed OpenAI path (#2365) and validates it itself. The OpenAI helper also sends `strict: true` for every schema, which the current schemas do not fit.
- **`strict: true` for OpenAI with `OpenAIJsonSchemaTransformer(strict=True)`.** Rejected: it marks every property as required, so the model must fill each optional field. pydantic-ai sends strict only for a schema that already fits.
- **A hand-written transform or capability table.** Rejected by rule 3 of AGENTS.md: pydantic-ai and the Anthropic SDK maintain both.

## Risks

- A schema that passes the Anthropic limits today can pass them later only while it stays under 24 optional and 16 union-typed parameters. A larger schema fails with the API's 400 error, which `chat_structured` reports as a failed request.
- The profile lists follow pydantic-ai's releases. A new model gets the constraint when the pin of pydantic-ai moves.

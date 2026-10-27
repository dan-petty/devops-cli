# Design

## Context

The `ai.llm.dispatch` inference span writes `gen_ai.response.model` in one place, `_set_response_span_attributes` in `src/devops_cli/ai/client/unified.py`. Today it copies `LLMResponse.model`, the model the reply body names, which for a hosted gateway call is the route name the client asked for, such as `devops-chat`. Since #2031, `LLMResponse.served_model` already carries the deployment model the gateway reply header `x-litellm-model-name` names, and the spend path in the same module already prefers `served_model` over `model` when it resolves a pricing model. See proposal.md for the motivation.

## Goals / Non-Goals

**Goals:**

- Record `gen_ai.response.model` as the deployment model that served a gateway call.
- Keep `gen_ai.response.model` as the reply-body model when the gateway names no deployment model.
- Leave `gen_ai.request.model` and `ai.llm.stream` unchanged.

**Non-Goals:**

- Changing what `LLMResponse.model` holds, what the spend path resolves, or what the request model key records.
- Introducing a `gen_ai.response.model` on the streaming span.

## Decisions

- **Resolve the response model where the span already writes it.** `_set_response_span_attributes` takes `served_model` when it is present and otherwise `model`, mirroring the spend fallback two functions below. This keeps the single writer of the response model key the only writer, so the request's tokens are counted once and no second attribute writer appears.
  - Rejected: overwriting `LLMResponse.model` with the header value in `_parse_compat_response`. The evidence that rejects it is that `LLMResponse.model` is the reply-body model other code reads as a fallback, and the span writer is the only place that should choose the response model key; rewriting the response field changes observable data beyond the span and would require re-checking every reader of `res.model`.
  - Rejected: setting the attribute where the response is built in the provider module. The evidence that rejects it is that the span is the owner of span attributes; a second writer there would split the response model decision across two files and risk the two keys disagreeing.

## Risks / Trade-offs

- A dashboard that grouped by `gen_ai.response.model` saw the route name and now sees the deployment model. The GenAI conventions define the key as the model that generated the response, so the new value is the one the convention asks for; a group by route name is `gen_ai.request.model`.

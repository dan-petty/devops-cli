# Design: Claude Provider Modernization with Anthropic SDK

## Context
See `proposal.md` for motivation. `ClaudeProviderMixin` in `src/devops_cli/ai/client/claude.py` constructs HTTP requests manually. It uses obsolete model names, hard-coded model name string checks, and custom SSE decoders.

## Goals / Non-Goals

**Goals:**
- Delegate Claude message generation and streaming to the official Anthropic SDK (`anthropic.Anthropic`).
- Supply the factory-built HTTP client from `_shared_client()` to `anthropic.Anthropic(http_client=...)`.
- Resolve model capabilities via `client.models.retrieve(model)` with process-level caching.
- Emit adaptive thinking payloads (`thinking={"type": "adaptive"}`) with `output_config.effort` when supported.
- Emit identical sampling parameters across streamed and unstreamed requests only when supported.
- Enforce mandatory `ai.model` configuration for provider `claude`.

**Non-Goals:**
- Modify OpenAI, Copilot, or Ollama provider implementations.
- Introduce compatibility shims for obsolete Claude 3 models.

## Decisions

### Decision 1: Use official Anthropic SDK client
`ClaudeProviderMixin` constructs an `anthropic.Anthropic` client instance. It passes `http_client=self._shared_client()` and `max_retries=0`.

- *Rejected alternative*: Maintain hand-written Anthropic REST payloads and SSE decoding.
  - *Evidence rejecting alternative*: Current models use adaptive thinking and reject obsolete `budget_tokens` and sampling parameters with HTTP 400. Hand-written protocol parsers violate rule 3 of `AGENTS.md`.
- *Rejected alternative*: Route Claude requests through Pydantic AI direct facades.
  - *Evidence rejecting alternative*: Issue 1852 deleted dead Pydantic AI facades because `LLMClient` serves as the sole model seam.

### Decision 2: Dynamic capability discovery with process caching
Model capabilities are retrieved via `client.models.retrieve(model_name)` and cached in memory. Explicit `supports_reasoning` configuration overrides discovered thinking capability.

- *Rejected alternative*: Model name pattern matching (e.g. `claude-3-7` or `:thinking`).
  - *Evidence rejecting alternative*: Anthropic retired Claude 3.5 and 3.7. Static name checks fail on modern models like Claude Opus 4.7 and Claude Sonnet 5.

### Decision 3: Mandatory model configuration
Empty or unset `ai.model` configuration raises a `ConfigurationError` naming `ai.model`.

- *Rejected alternative*: Retain fallback default model `claude-3-5-sonnet`.
  - *Evidence rejecting alternative*: Anthropic retired `claude-3-5-sonnet`. Falling back to retired models causes runtime failures.

## Risks / Trade-offs

- [Models API overhead] → The client caches capability lookups in-memory per model name for the process lifetime.
- [SDK exception wrapping] → Catch `anthropic.APIConnectionError` and `anthropic.APIStatusError` and map them through `self._connection_error` and `self._provider_http_error`.

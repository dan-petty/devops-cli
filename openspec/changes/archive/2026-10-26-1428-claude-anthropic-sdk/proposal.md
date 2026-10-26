# Proposal: Claude Provider Modernization with Anthropic SDK

## Why
This change resolves #1428. The Claude provider constructs HTTP requests manually and uses retired models, obsolete thinking payload schemas, and incompatible sampling options. Current Anthropic models reject these requests with HTTP 400.

## What Changes
- Replace manual HTTP client requests in `ClaudeProviderMixin` with official `anthropic.Anthropic` client calls.
- Enforce mandatory `ai.model` configuration for provider `claude`, raising a `ConfigurationError` when empty.
- Remove hard-coded model name heuristics (`claude-3-*`, `:thinking`) and retired `budget_tokens` parameters.
- Query and cache model capabilities via the Models API (`client.models.retrieve`), allowing `supports_reasoning` configuration overrides.
- Transmit adaptive thinking payloads (`{"type": "adaptive"}`) with `output_config.effort` when supported by model capabilities.
- Ensure consistent `temperature` and `top_p` sampling transmission across streamed and unstreamed requests only when the model supports sampling.
- Delete obsolete event framing functions `_CLAUDE_EVENT_FRAMES` and `_claude_stream_frame`.
- Add `anthropic==1.12.1` to project dependencies in `pyproject.toml`.

This change fits one pull request.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `ai-model-sampling`: add requirements for Claude provider capability resolution, adaptive thinking options, and model presence enforcement.

## Impact
- `src/devops_cli/ai/client/claude.py`: modernized to use Anthropic SDK for messages and streaming.
- `src/devops_cli/ai/client/streaming.py`: removed obsolete Claude SSE event decoders.
- `src/devops_cli/ai/client/unified.py`: enforced non-empty `ai.model` validation for Claude provider.
- `pyproject.toml`: declared `anthropic==1.12.1` direct dependency.
- `openspec/specs/ai-model-sampling/spec.md`: updated specification with capability delta.

## Feasibility
The premise was confirmed against the live runtime environment. The `anthropic` SDK version 1.12.1 is present in `uv.lock`. Inspection of `anthropic.Anthropic.__init__` confirmed support for `http_client` and `max_retries=0`. Direct testing with `httpx2.MockTransport` confirmed that `client.models.retrieve` returns model capabilities and `client.messages.create` and `client.messages.stream` correctly format adaptive thinking and extra body parameters.

## Existing Tool Considered
The official `anthropic` Python SDK (version 1.12.1) is used directly rather than maintaining bespoke Anthropic REST and SSE decoders. This change deletes manual header generation, payload builders, and SSE frame parsers in `src/devops_cli/ai/client/claude.py` and `src/devops_cli/ai/client/streaming.py`.

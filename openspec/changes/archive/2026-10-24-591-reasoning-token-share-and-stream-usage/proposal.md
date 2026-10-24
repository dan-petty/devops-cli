# Proposal

## Why

Issue #591: devops-cli does not record reasoning tokens or provider-reported stream usage.
Stream spend hand-counts joined chunks and inflates completion tokens without a reasoning split.
Multi-node Ollama streams record every configured host rather than the leased node.
Streams that close or abort early fail to record spent tokens because exceptions do not catch generator exits.

## What Changes

- devops-cli requests provider stream usage by sending `stream_options: {"include_usage": true}` on OpenAI-compatible streams.
- The stream parser extracts stream token usage from OpenAI chunks, Ollama final lines, and Claude delta events.
- Token counting remains only as a fallback when a stream provides no usage metrics.
- A multi-node Ollama stream records the specific leased node as its server in the spend ledger.
- A stream generator records spent tokens in a `finally` block when a consumer abandons or interrupts the stream.
- `LLMResponse` carries `reasoning_tokens` beside existing token fields.
- `ai/client/openai.py` reads `reasoning_tokens` from `usage.completion_tokens_details.reasoning_tokens`.
- Native Ollama and Claude estimate reasoning tokens from `LLMResponse.thinking` when present.
- The spend ledger adds a `reasoning_tokens` column to `ai_spend_records` and updates `track_request_spend`.
- Telemetry instruments emit `AI_TOKENS_TOTAL` with `type="reasoning"` as a subset of completion tokens.
- Telemetry spans record `gen_ai.usage.reasoning.output_tokens` from OpenTelemetry semantic conventions.
- `devops ai cost report` displays a reasoning-share column, including in the `--by backend` view.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-spend-pricing`: record stream usage from providers, track reasoning tokens in the spend ledger, and report reasoning share.

## Impact

- Code: `src/devops_cli/ai/client/models.py`, `src/devops_cli/ai/client/streaming.py`, `src/devops_cli/ai/client/network.py`, `src/devops_cli/ai/client/openai.py`, `src/devops_cli/ai/client/ollama.py`, `src/devops_cli/ai/client/claude.py`, `src/devops_cli/ai/client/unified.py`, `src/devops_cli/ai/spend/models.py`, `src/devops_cli/ai/spend/ledger.py`, and `src/devops_cli/commands/ai_cost.py`.
- Manifests: none.
- Documents: command references updated with `devops docs generate --sync-readme`.
- Tests: `tests/test_ai_streaming.py`, `tests/test_ai_spend_ledger.py`, `tests/test_ai_spend_cli.py`, and `tests/test_ai_client_telemetry.py`.

## Feasibility

- OpenAI-compatible stream protocol: `stream_options: {"include_usage": true}` delivers usage in final chunks before completion.
- Ollama streaming protocol: the terminal frame with `done: true` carries `prompt_eval_count` and `eval_count`.
- Anthropic streaming protocol: `message_start` events provide input tokens and `message_delta` events provide output tokens.
- OpenTelemetry semantic conventions: `GEN_AI_USAGE_REASONING_OUTPUT_TOKENS` is confirmed in `opentelemetry.semconv._incubating.attributes.gen_ai_attributes`.
- Leased node tracking: `acquire_ollama_slot` returns the single leased endpoint string.
- Generator exit handling: `finally` blocks execute reliably on `GeneratorExit` and `KeyboardInterrupt`.

## Existing Tool Considered

Provider stream options and OpenTelemetry semantic conventions provide standard interfaces.
SQLite table alteration handles schema evolution in place.
No custom token estimator or external character counter is built.
Internal manual token counting is replaced by provider-reported usage.

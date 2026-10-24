# Proposal

## Why

Issue #590 shows that thinking-stream sanitizers start only in the emitting state, pass unopened closing tags through as answer text, omit thought buffer limits, and fail to report unclosed streams at stream termination.

## What Changes

This change implements a unified finite state machine core for thinking-stream sanitization:
- Add a shared finite state machine core behind `ThinkingStreamProcessor` and `StreamingTokenProcessor`.
- Count and strip unopened closing tags encountered while in the emitting state.
- Cap thought buffers at 65,536 characters, discarding excess thought characters and counting discarded characters.
- Detect and report unclosed streams at end of file by setting `unclosed_stream = True`.
- Support model-specific `initial_state` (`emitting` or `thinking`) and `thinking_tags` configuration via `ModelProfileSpec`.
- Expose `unopened_close_tags`, `unclosed_stream`, and `discarded_thought_chars` on `to_dict()` and record them on LLM stream trace spans.
- Run `strip_think_blocks` and `extract_think_blocks` through the shared finite state machine core.
- Delete the legacy alias `StreamingReasoningSanitizer`.

This change fits one pull request.

## Capabilities

### New Capabilities
- `thinking-stream`: Sanitize streaming and batch thinking blocks with configurable initial state, unopened tag counting, unclosed stream detection, and thought character caps.

### Modified Capabilities
None.

## Impact

- AI streaming: Replaces duplicate state logic across `devops_cli.ai.thinking_stream` and `devops_cli.ai.client.streaming`.
- AI profiles: Adds `_apply_profile_spec`, `get_model_thinking_tags`, and `supports_thinking` support for thinking configuration in `devops_cli.ai.profiles`.
- Telemetry: Adds `unopened_close_tags`, `unclosed_stream`, and `discarded_thought_chars` attributes to the stream trace span in `devops_cli.ai.client.unified`.
- Deprecations: Deletes the `StreamingReasoningSanitizer` alias.

## Feasibility

I confirmed the premise against the real system:
- Fed `['Deciding what to commit.', '</think>', 'git commit -m x']` into `ThinkingStreamProcessor(show_thinking=False)`, `StreamingTokenProcessor()`, and `strip_think_blocks()`, and confirmed all three emitted `'Deciding what to commit.</think>git commit -m x'` without tracking unopened tags.
- Fed 100,000 thought characters to `ThinkingStreamProcessor` and `StreamingTokenProcessor`, and confirmed neither capped the thought buffer nor counted discarded characters.
- Fed unclosed thought blocks into `ThinkingStreamProcessor` and `StreamingTokenProcessor` followed by `flush()`, and confirmed neither set `unclosed_stream=True` in `to_dict()`.
- Verified `pydantic-ai` 2.35.0 matches tags only across full deltas and cannot handle split tags across token chunks.

## Existing Tool Considered

`pydantic-ai` provides basic thinking parts management but does not support split tags across streaming chunk boundaries or configurable thought character caps. Implementing the unified finite state machine core internally requires approximately 120 lines of code, 4,000 tokens of agent context and 15 minutes of elapsed time. This change deletes duplicate state processing logic across `StreamingTokenProcessor` and `ThinkingStreamProcessor`, and deletes the `StreamingReasoningSanitizer` alias.

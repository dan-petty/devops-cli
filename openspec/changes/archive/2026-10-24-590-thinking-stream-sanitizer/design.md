# Design

## Context

See proposal.md - Why. Current streaming and batch reasoning extraction relies on separate FSM implementations in `ThinkingStreamProcessor` and `StreamingTokenProcessor`, which share common limitations around unopened tags, stream truncation, and buffer bounds.

## Goals / Non-Goals

**Goals:**
- Provide a single, well-tested finite state machine core that powers `ThinkingStreamProcessor`, `StreamingTokenProcessor`, `strip_think_blocks`, and `extract_think_blocks`.
- Enforce the 65,536-character thought buffer cap without raising exceptions, tracking discarded characters via `discarded_thought_chars`.
- Correctly count unopened close tags via `unopened_close_tags` and prevent leaking them into content.
- Accurately report stream truncation at EOF via `unclosed_stream = True`.
- Configure model-level initial state (`emitting` or `thinking`) and thinking tags through `ModelProfileSpec` in `devops_cli.ai.profiles`.
- Expose metrics in `to_dict()` and record them on `ai.llm.stream` trace spans.

**Non-Goals:**
- Replacing token chunking or network streaming adapters.
- Raising exceptions when thought caps are exceeded.
- Maintaining compatibility shims such as `StreamingReasoningSanitizer`.

## Decisions

### Decision 1: Shared ThinkingFSM core behind public processors
Implement a dedicated `ThinkingFSM` state machine in `devops_cli.ai.thinking_stream` that encapsulates token buffer scanning, split-tag overlap detection, state transitions, thought capping, and metric counting. Both `ThinkingStreamProcessor` and `StreamingTokenProcessor` delegate parsing to this core.

- *Rejected Alternative*: Adopting `pydantic-ai` internal tag matching.
  - *Evidence*: `pydantic-ai` 2.35.0 matches tags only across full stream deltas (`_parts_manager.py:200,214`) and emits unclosed thought blocks as `TextPart` (`_thinking_part.py:24-26`), causing 42 existing split-tag tests to fail.

### Decision 2: Discard and count excess thought characters
When accumulated thought content exceeds `max_thought_chars` (default 65,536), the FSM core retains only the first `max_thought_chars` characters and increments `discarded_thought_chars` for any excess.

- *Rejected Alternative*: Raising a buffer overflow exception.
  - *Evidence*: Raising exceptions aborts user chat interactions and LLM review pipelines midway when verbose models output extensive reasoning chains. Discarding with telemetry preserves the user-visible answer while alerting on oversized thoughts.

### Decision 3: Configure initial state and tags via `ModelProfileSpec`
Allow model profile dictionaries and functions in `devops_cli.ai.profiles` to specify `initial_state: "thinking"` and `thinking_tags: (open, close)`. `_apply_profile_spec` merges these specifications against defaults, defaulting to `emitting` state and `("<think>", "</think>")`.

- *Rejected Alternative*: Hardcoding initial state per provider or in Kubernetes gateway configmaps.
  - *Evidence*: Model inference parameters and thinking behaviors vary across models on the same gateway instance (e.g. DeepSeek-R1 vs Qwen vs Mistral). Profile specs apply directly during model instantiation without requiring Kubernetes redeployments.

## Risks / Trade-offs

- [Risk]: Setting `initial_state: "thinking"` on a model that never outputs thinking tags could suppress output.
  → *Mitigation*: The default initial state is `emitting`. Only models explicitly configured with `initial_state: "thinking"` start in the thinking state, and unclosed streams preserve buffered content at EOF.
- [Risk]: Large inputs with multiple split tags could introduce parsing overhead.
  → *Mitigation*: The FSM core uses linear index search and suffix overlap checking with bounded window lengths equal to tag lengths.

# Design

## Context

See `proposal.md` for motivation.
The system streams LLM completions without capturing provider-reported token usage.
Reasoning tokens are not separated from completion tokens in the spend ledger.

## Goals / Non-Goals

**Goals:**
- Request and parse provider-reported usage across OpenAI, Ollama, and Claude streams.
- Attribute multi-node Ollama stream spend to the leased server node.
- Ensure stream spend is recorded in a `finally` block on normal completion, error, or early exit.
- Store reasoning tokens in the SQLite spend ledger schema and report reasoning share.

**Non-Goals:**
- Implement per-route token budgets or reasoning caps (addressed in #479).
- Add custom token counters when provider usage is available.

## Decisions

### Decision: Transmit stream usage through ContextVar objects
- **Choice**: Use ContextVar objects in `network.py` (`stream_usage`, `stream_server`) to transport stream metadata to spend recording.
- **Rationale**: Python generators yield chunks in caller loops where return values are lost and wrapper layers intervene. Context variables maintain context-local state cleanly.
- **Alternative Considered**: Returning metadata in a custom generator wrapper object.
  - *Evidence for rejection*: Wrapping generators breaks compatibility with standard Python generator iteration and requires modifying every caller.

### Decision: Handle stream spend recording in a finally block
- **Choice**: Move `_record_stream_spend` execution into a `finally` block with a single-execution guard.
- **Rationale**: `GeneratorExit` and `KeyboardInterrupt` inherit from `BaseException` rather than `Exception`. A `finally` block guarantees spent tokens are recorded when consumers abandon streams.
- **Alternative Considered**: Catching `BaseException` directly.
  - *Evidence for rejection*: Catching `BaseException` requires re-raising logic across multiple blocks and risks swallowing system exits.

### Decision: Schema evolution with ALTER TABLE in _ADDED_COLUMNS
- **Choice**: Add `reasoning_tokens` via `_ADDED_COLUMNS` in `src/devops_cli/ai/spend/ledger.py`.
- **Rationale**: Maintains consistency with existing migrations for `served_by`, `stage`, and `pricing_source`.
- **Alternative Considered**: Recreating the table or creating a separate reasoning table.
  - *Evidence for rejection*: Recreating the table loses user spend records; a separate table adds join overhead to every query.

## Risks / Trade-offs

- [Risk]: Some providers do not report reasoning tokens directly.
  → Mitigation: Fall back to estimating tokens over `LLMResponse.thinking` via `count_tokens` when thinking text is present.
- [Risk]: Double-counting tokens in queries.
  → Mitigation: Keep reasoning tokens as a subset of completion tokens and avoid summing across token types.

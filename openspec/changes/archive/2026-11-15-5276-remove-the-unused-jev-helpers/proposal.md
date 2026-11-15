# Proposal

## Why

Six functions of `src/devops_cli/ai/jev.py` had no caller in `src`, and five of them had no planned caller and no `DecisionPoint` of ADR 0020. Their thresholds were guesses, which ADR 0019 rule 4 forbids (#5276).

## What Changes

- Remove `select_skill_with_jev`, `gate_tool_call_with_jev`, `judge_with_jev`, `create_jev_judge_evaluators` and `filter_rag_passages_with_jev`, their result types, their rubrics and their tests. Keep `route_with_jev` while #4284 is open.
- Add one dated Status History line to ADR 0019 and ADR 0020.
- Keep the `auto` mode (`build_auto_tool_model`) and its test.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. The change removes code that nothing called.

## Impact

- Code: `src/devops_cli/ai/jev.py`
- Tests: `tests/ai/test_jev.py`, `tests/ai/test_jev_one_model_many_requests.py`
- Documents: `docs/adr/0019-...`, `docs/adr/0020-...`

## Feasibility

- Read on `origin/main`, 2026-11-15. `git grep -w` finds no caller in `src` for the five names.
- `uv run pytest tests/ai` passes after the change, with 3806 tests.
- `uv run pytest tests/docs/test_docs_adr_records.py` passes with the two lines.

## Existing Tool Considered

Not applicable: the change removes code. Cost: about 1,500 tokens, and no upkeep.

## Dependencies

None.

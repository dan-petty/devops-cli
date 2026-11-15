# Proposal

## Why

`CONST_AI_JEV_CONTEXT_WINDOW` was 262,144, but genai-prices gives `context_window=32000` for `typesafe/jev-1.14`. The completeness check capped the diff at a fourth of the constant, 65,536 tokens, so it could send a diff twice the window of the model (#5209).

## What Changes

- Add `context_window` to `src/devops_cli/ai/jev.py`: it reads the window of `CONST_AI_JEV_MODEL` from genai-prices, and the constant is the fallback for a model that the data does not name.
- Add `max_diff_tokens`, a fourth of that window, and use it in `jev_completeness.py` in place of `CONST_ROADMAP_JEV_MAX_DIFF_TOKENS`.
- Remove `CONST_ROADMAP_JEV_MAX_DIFF_TOKENS`; the constant was the only reader of the wrong window.
- Trim the two `change-1653` eval diffs under the 8,000-token cap.
- Add the window test in `tests/ai/test_jev.py`.

## Capabilities

### New Capabilities

- `jev-limits`: the context window and the diff cap of the Jev completeness check.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/ai/jev.py`, `src/devops_cli/roadmap/jev_completeness.py`, `src/devops_cli/config/constants.py`
- Tests: `tests/ai/test_jev.py`, `tests/roadmap/test_jev_completeness.py`, `tests/roadmap/test_jev_completeness_eval.py`, `tests/roadmap/test_roadmap_limit_classes.py`
- Fixtures: `tests/fixtures/roadmap_eval/completeness/change-1653-complete/draft.diff`, `change-1653-hunk-removed/draft.diff`

## Feasibility

- Read on `origin/main`, 2026-11-15. `src/devops_cli/config/constants.py:2980:CONST_AI_JEV_MODEL` names `typesafe/jev-1.14`, and `genai_prices` is a dependency.
- `genai_prices.data_snapshot.get_snapshot().providers` lists provider `typesafe` with model `jev-1.14.0` and `context_window=32000`.
- `src/devops_cli/roadmap/jev_completeness.py:164` reads the diff cap.
- `uv run pytest tests/ai/test_jev.py tests/roadmap/test_jev_completeness.py tests/roadmap/test_jev_completeness_eval.py` passes after the change.

## Existing Tool Considered

genai-prices is the existing dependency and already holds the model data. The change reads it and removes one constant: about 2,000 tokens to build and 200 a quarter to keep.

## Dependencies

None.

# Design: #5464 fix(roadmap): the refine proposal caps its context with a job constant

## Architecture
- `src/devops_cli/config/constants.py`: Define `CONST_ROADMAP_REFINE_CONTEXT_MAX_TOKENS: Final[int] = 20_480`.
- `src/devops_cli/roadmap/refine/refine.py`:
  - Define `_WINDOW_SHARE_CONTEXT: Final[int] = 2`.
  - In `plan_refine`: `max_tokens = min(CONST_ROADMAP_REFINE_CONTEXT_MAX_TOKENS, window // _WINDOW_SHARE_CONTEXT)`.
  - In `collect_context`: Returns `RefineContext(str)` carrying `before` and `after` token counts.
  - In `RefinedItem`: Fields `context_before: int = 0` and `context_after: int = 0`.
  - In `_log_attempt`: Logs `context_before` and `context_after` on the refine job result line.

## Compatibility & Safety
- `RefineContext` subclasses `str`, maintaining backward compatibility for all callers and JSON serialization.
- `FIRST_PASS` verification is unaffected because unknown keys do not prevent first pass determination.

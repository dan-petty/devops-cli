# Design

## Decisions

- **Two-state status instead of three-state status**:
  `_evaluate_tiered_status` returns only `completed` or `failed`. When every sub-agent result has status `success`, it returns `completed`. Otherwise, it returns `failed`. Both searches share the same root path and fail together.
- **Single prefix in `_summarize_search`**:
  With `partial` removed, status is either `completed` or `failed`. Non-failed statuses always use the prefix `Found`.

## Rejected alternatives

- **Keep partial status**:
  Rejected. Pre-1.0 alpha software keeps no dead code or zombie branches. Code with no caller or reachable public input must be removed.

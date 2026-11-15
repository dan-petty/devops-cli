# Proposal: #5464 fix(roadmap): the refine proposal caps its context with a job constant

## Why
Closes #5464.
The refine proposal call caps repository context with the context window of the `analysis` task. In production, this window is 256,000 tokens. The cap has no effect in practice. Item bodies that cite large files cause large context payloads, high token burn, latency, and potential timeouts. Stage bounds the same context with `CONST_ROADMAP_STAGE_CONTEXT_MAX_TOKENS` (20,480).

## What Changes
1. Add `CONST_ROADMAP_REFINE_CONTEXT_MAX_TOKENS` (20,480) to `src/devops_cli/config/constants.py`.
2. Define `_WINDOW_SHARE_CONTEXT = 2` in `src/devops_cli/roadmap/refine/refine.py` and compute the context token limit as `min(CONST_ROADMAP_REFINE_CONTEXT_MAX_TOKENS, window // _WINDOW_SHARE_CONTEXT)`.
3. Provide `RefineContext` tracking context tokens before and after the cap.
4. Record `context_before` and `context_after` on the refine job result line.

## Capabilities
- `roadmap.refine`: bounded context collection for refinement proposal requests.
- `roadmap.refine`: result line records context token counts before and after truncation.

## Impact
- Context token burn in refine proposal calls is capped to at most 20,480 tokens.
- Telemetry captures context tokens before and after the cap on Loki result lines.

## Feasibility
- Verified on `origin/main` that stage uses `min(CONST_ROADMAP_STAGE_CONTEXT_MAX_TOKENS, window // _WINDOW_SHARE_CONTEXT)`.
- Verified that `truncate_to_token_limit` cleanly enforces the token budget.

## Existing Tool Considered
`truncate_to_token_limit` cuts the context. The change sets the bound only. No new tool is necessary.

# Proposal: #4864

## Why
A refused alternatives reply is not logged with its reason or counted, so the alternatives success rate is not known; one Ready item holds `alternatives.failed_error=RefusedReply` now. The item waits 3 days for the next try with no return.

## What Changes
- Write a stable reason code of a refused reply in the `reason` field of the alternatives result line.
- Record the reason code in the item's job record under `alternatives.failed_reason` while keeping `alternatives.failed_error=RefusedReply`.
- Clear `alternatives.failed_reason` when a check is written.
- Register the decision point `alternatives.reply_fixable` with `asks_model=False` and a rule that reads its fixable code table from its cuts file `src/devops_cli/roadmap/alternatives_cuts.json`.
- In mode `shadow`, record the decision band (`review` or `continue`) on the result line and make no second model call.
- In mode `on`, send a fixable refusal back to the model once through `output_check` when its code is not already in the item's job record.
- Keep the 3-day retry wait for repeated refusal codes and not-fixable failures.
- Keep the one return inside the attempt budget of 10 searches and 30 fact reads.

## Capabilities
- `roadmap-alternatives`: classify refused replies as fixable or not, record refusal codes, and send fixable refusals back once.

## Impact
- Increases alternatives check success rate by fixing simple form defects in one retry turn.
- Surfaces refusal reason codes and decision bands in result lines for observability.

## Feasibility
- Verified `_retry_once` and `output_check` in `refine_investigation.py` handle one return with `ModelRetry`.
- Verified `DecisionPoint` with `asks_model=False` and rule resolver integrates with `Registry` and `POINT_CUTS`.

## Existing Tool Considered
- jd/tenacity (https://github.com/jd/tenacity): already in use in repository for network retries, but lacks decision point integration, reason classification, job record updates, and shared run budget enforcement. Built at written cost of ~0.5M tokens, 3 hours.

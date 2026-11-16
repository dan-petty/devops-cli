# Design: #4864

## Context
When the alternatives job refuses a reply, it records `alternatives.failed_error=RefusedReply` and waits 3 days for the next try. The refusal reason is not recorded as a code, and the model is not given an opportunity to repair simple form errors.

## Decisions

### Decision 1: Stable reason codes on result line and in job record
- Form refusal reasons from `_refusal` map to stable codes:
  - `alternatives_reason_skip_only` -> `skip_only`
  - `alternatives_reason_job_verdict` -> `job_verdict`
  - `alternatives_reason_no_search` -> `no_search`
  - `alternatives_reason_no_tool` -> `no_tool`
  - `alternatives_reason_no_facts` -> `no_facts`
  - `alternatives_reason_url` -> `url`
  - Unpaired markers in body -> `marker`
- Stopped investigation reasons:
  - `schema_broken` -> `schema_broken`
  - `output_limit` -> `output_limit`
  - `invalid_arguments` -> `invalid_arguments`
  - `UsageLimitExceeded` -> `timeout`
- The result line sets `result=refused` and `reason=<code>`.
- The job record sets `alternatives.failed_reason=<code>` and keeps `alternatives.failed_error=RefusedReply`.
- Successful checks clear `alternatives.failed_reason=None`.

### Decision 2: Decision point `alternatives.reply_fixable`
- Register `alternatives.reply_fixable` in `src/devops_cli/roadmap/alternatives_reply_fixable.py`.
- Cuts file lives at `src/devops_cli/roadmap/alternatives_cuts.json` with step `alternatives.reply_fixable`.
- The cuts file report section holds `fixable_codes`: `["skip_only", "job_verdict", "no_search", "no_tool", "no_facts", "url", "schema_broken"]`.
- The rule checks whether `code in fixable_codes` and `code != earlier_code`.
  - Fixable and not repeated: band `review`.
  - Non-fixable or repeated: band `continue`.
- Decision point properties: `asks_model=False`, `counts_only=True`, rule resolver only.

### Decision 3: Shadow mode and on mode
- In mode `shadow`:
  - The decision point runs and logs its decision.
  - The result line includes `band=<band>`.
  - The job does not retry and keeps the 3-day wait.
- In mode `on`:
  - When band is `review` and `returns == 0`, `output_check` returns the refusal message.
  - `_retry_once` raises `ModelRetry(message)` so the model repairs the reply.
  - If repaired, a verdict check is written with `returns=1`.
  - If band is `continue`, no return occurs, and the 3-day wait is kept.

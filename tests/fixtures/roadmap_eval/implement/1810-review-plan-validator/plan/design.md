# Design

## Context

See `proposal.md` for problem motivation and background.
`src/devops_cli/review/analysis.py` defines two model-driven review jobs:
- `_execute_single_group_job`: validates group replies through `_judge_group_reply`, enforces `max_retries=0`, and catches `ReplyRejectedError` (#1013).
- `run_review_plan_job`: calls `llm_client.chat(...)` without a validator, allowing unverified or invalid plans to enter the response cache.

## Goals / Non-Goals

**Goals:**
- Validate review plan replies before the response cache stores them.
- Send review plan chat requests with `max_retries=0`.
- Catch `ReplyRejectedError` to inspect the rejected reply and record rejection reasons.
- Share the chat-and-judge workflow between `_execute_single_group_job` and `run_review_plan_job`.
- Add test coverage driving `run_review_plan_job` through a real `LLMClient` with mock transport and isolated disk cache.

**Non-Goals:**
- Modify G10 plan validation rules in `verify_review_plan`.
- Modify pipeline orchestrator stages or stage flag defaults.

## Decisions

### 1. Extract shared `_chat_and_judge` execution helper

Both jobs follow the same workflow:
1. Define a `judge` function returning `(parsed_output, rejection_reasons)`.
2. Wrap `judge` in an `accept` closure that caches verdicts by reply text.
3. Call `llm_client.chat(..., max_retries=0, validator=accept)`.
4. Catch `ReplyRejectedError` and extract `rejected.reply`.
5. Check if `finish_reason == CONST_FINISH_REASON_LENGTH` to set `reply-truncated`.
6. Return `(verified_output, reasons, is_cached)`.

Extracting `_chat_and_judge` avoids duplication across the two jobs.

*Alternative considered:* Copy the chat, validator, and exception handling directly into `run_review_plan_job`.
*Evidence rejecting alternative:* Copying duplicates 30 lines of error-handling and cache-checking logic. Issue #1810 explicitly directs sharing the step.

### 2. Parse and verify review plan output inside `_judge_plan_reply`

`_judge_plan_reply` performs candidate extraction, Pydantic schema validation (`ReviewPlanOutput`), and G10 checks (`verify_review_plan`).
If any step fails, it returns `None` and the rejection reason list.

*Alternative considered:* Only validate schema in the validator and run `verify_review_plan` after `chat` returns.
*Evidence rejecting alternative:* A model reply that passes schema checks but violates G10 plan rules would be accepted by the validator and saved in the cache.

## Risks / Trade-offs

- [Model network or runtime errors] → `run_review_plan_job` catches runtime exceptions (`RuntimeError`, `ValueError`, `OSError`, `TimeoutError`, etc.) and records `model-call-error`.
- [Empty response content] → `LLMClient` raises `AIClientError` when response content and thinking are empty. Handled as `model-call-error` after one call without retries.

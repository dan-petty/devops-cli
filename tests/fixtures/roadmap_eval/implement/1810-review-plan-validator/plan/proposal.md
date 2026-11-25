# Proposal

## Why

Issue #1810: `run_review_plan_job` in `src/devops_cli/review/analysis.py` sends a review plan prompt with `llm_client.chat(...)` without a validator, without `max_retries=0`, and without handling `ReplyRejectedError`.
The response cache would store a model reply that does not parse or that fails `verify_review_plan` checks, and the client could resend an unusable reply up to four more times.
Pull request #1812 resolved this defect for group analysis jobs (#1013), but left `run_review_plan_job` unvalidated.

## What Changes

- Give `run_review_plan_job` the same shape as `_execute_single_group_job`: a judge function that parses the output and runs `verify_review_plan` once, passes `max_retries=0` and a validator to `chat`, and handles `ReplyRejectedError`.
- Share the chat-and-judge execution step between `_execute_single_group_job` and `run_review_plan_job` through a helper function in `src/devops_cli/review/analysis.py`.
- Add test coverage driving `run_review_plan_job` through a real `LLMClient` with a mock transport and test cache directory, verifying that unparseable replies and check failures are rejected after one dispatch and never cached.
- The change sets `skip_specs: true` in `.openspec.yaml` because this change fixes an internal review pipeline job and alters no user-facing CLI command or schema.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/review/analysis.py`.
- Tests: `tests/test_review_group_analysis.py`.

## Feasibility

- Premise confirmed against `src/devops_cli/review/analysis.py`: lines 1354-1360 call `llm_client.chat(...)` with only `temperature`, `top_p`, and `seed`, running verification only after the cache stores the reply.
- Premise confirmed against `src/devops_cli/ai/client/unified.py`: `chat(...)` supports `validator` and `max_retries=0`, discards unvalidated replies from the cache, and raises `ReplyRejectedError` carrying the raw `LLMResponse`.

## Existing Tool Considered

`LLMClient.chat` already provides response validation and cache rejection via `validator` and `max_retries=0`.
`verify_review_plan` already implements all review plan G10 rules.
Sharing the chat-and-judge logic between jobs uses existing internal components and deletes duplicate response checking code.
No external tool or library is required.

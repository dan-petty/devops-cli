# Proposal: #4587

## Why

The record `implement.spend` keeps only one figure for each step: the input tokens of its first request (#3499). The totals of the record add all steps of all Jobs of the item, so a reader cannot tell which step or which attempt used the tokens. The trace `implement.trace` drops its oldest model events when a run is long (#4393), so the trace cannot give these figures either. In a study of implement runs, the median first request was 27,924 tokens, and the 97,821 tokens in #4385 is a request from the middle of a run. Without the largest request of each step, the record cannot show this. The investigations #4385 and #4386, and the work of #4075 and #4394, need these figures for each step. Closes #4587.

## What Changes

- The entry of each step in `implement.spend.steps` also holds `requests`, `input_tokens`, `output_tokens`, `repair_rounds` and `largest_request_tokens` of the step. The entry keeps `step`, `first_request_tokens` and the optional `extension`.
- `StepOutcome` and the turn record `_Run` get the field `largest_request_tokens`: the largest `usage.input_tokens` of one reply of the step, over all turns, repair rounds and tiers.
- The budget count of the step and of the item does not change.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job`: the record keeps the tokens of each step.

## Impact

- Code: `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/roadmap/implement/implement_run.py`
- Tests: `tests/roadmap/implement/test_roadmap_implement_job_trace.py`
- Documents: `docs/roadmap/implement.md`
- The record grows by five numbers for each step. No setting, metric or request changes.

## Feasibility

- Confirmed in the source on origin/main 5f75d256: `_step_spend` in `implement_run.py` writes only `step`, `first_request_tokens` and the optional `extension`. `StepOutcome` already holds `requests`, `input_tokens`, `output_tokens` and `repair_rounds` of the step. `_run_turn` in `implement_step.py` has the usage of each reply of a turn, so it can give the largest request.
- Confirmed in pydantic-ai 2.59.0: `RequestUsage` has `input_tokens`, `output_tokens`, `cache_read_tokens` and `cache_write_tokens` for each reply.
- Confirmed that a streamed `FunctionModel` reports 50 input tokens for each request. So the test model reports an input that grows with the messages of the request, as a provider does, to make the largest request differ from the first.

## Existing Tool Considered

pydantic-ai `RequestUsage` gives the counts of each reply, and the job already sums them. This change only writes counts that the job already has, so no tool or library is necessary. Cost: about 60,000 input tokens and 10,000 output tokens to build, almost nothing to keep, and about 1 hour.

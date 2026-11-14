# Proposal

## Why

The spend hook of `build_agent` passes `server` and `served_model` but not `served_by`. The backend breakdown of the lifetime report keeps only rows with `served_by`, so the stage, refine and alternatives requests do not appear in it (#4716).

## What Changes

- The hook passes `served_by`, so the backend breakdown counts the request and prices it at the backend that served it.
- The two gateway price tests name a hosted backend, because a local gateway host makes the request local.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-spend-pricing`: A `build_agent` request names its served backend.

## Impact

- Code: `src/devops_cli/ai/client/factory.py`
- Tests: `tests/ai/client/test_agent_factory.py`

## Feasibility

- `track_request_spend` already takes `served_by`.
- The client reads the backend URL from the gateway header.
- Verification commands: `uv run devops ci test tests/ai/client/test_agent_factory.py` and `uv run devops ci --check --only lint,format,typecheck`.

## Existing Tool Considered

The ledger and the pricing registry already exist. The change passes one argument.

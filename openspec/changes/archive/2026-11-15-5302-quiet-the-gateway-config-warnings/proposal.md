# Proposal

## Why

The LiteLLM gateway config put its model-group and fallback wiring into the message that a client reads, and its comments described behaviour that v1.103.11 changed. An operator read the start-up `trusted_proxy_ranges` warning and the health column as faults (#5302).

## What Changes

- Set `expose_router_debug_in_errors: false` in `litellm_settings`, and remove `telemetry: false`, which v1.103.11 does not read.
- Add the comment that explains why `trusted_proxy_ranges` stays unset and the start-up WARNING is expected, and the comment that the empty health column is on purpose.
- Correct the hosted-group comment, and name the callable `embedding` group as the thirteenth `/v1/models` id.
- Rewrite the `DATABASE_URL` and `ENFORCE_PRISMA_MIGRATION_CHECK` comments, and remove `LITELLM_TELEMETRY`.
- Add `tests/k8s/test_llm_gateway_config.py`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. The change corrects the config and its comments.

## Impact

- Manifests: `k8s/llm/gateway/config.yaml`, `k8s/llm/gateway/deployment.yaml`
- Tests: `tests/k8s/test_llm_gateway_config.py`

## Feasibility

- Read on `origin/main`, 2026-11-15. LiteLLM 1.103.11 defaults `expose_router_debug_in_errors` to true, and no code reads `telemetry` or `LITELLM_TELEMETRY`.
- `uv run pytest tests/k8s/test_llm_gateway_config.py` passes with 3 cases.
- `uv run python -m tests.gate.k8s` passes.

## Existing Tool Considered

None; the change corrects values and comments.

## Dependencies

None.

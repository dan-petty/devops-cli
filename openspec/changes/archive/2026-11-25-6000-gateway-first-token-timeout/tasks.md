# Tasks

## 1. Native first-event timeout and retry on stalled gateway streams

> Kind: behavior

- [x] 1.1 Add failing tests in `tests/ai/models/test_gateway_call.py` and `tests/ai/client/test_roadmap_agent_run.py` for stalled keep-alive deadline (`setting == "first_event_timeout"`), single resend closing stalled stream, slow post-first-token continuation, default/resolved `first_event_timeout`, invalid timeout nesting in `AIConfig`, and `model_call_error` reporting `timed_out=True` on `ModelRequestTimeout`
  - Verification: `$ uv run pytest -q tests/ai/models/test_gateway_call.py tests/ai/client/test_roadmap_agent_run.py`
- [x] 1.2 Add `DEFAULT_AI_FIRST_TOKEN_TIMEOUT_SECONDS` and `AIConfig.first_token_timeout_seconds` with nesting validator, wire `first_token_timeout` via `GatewayCallModel` and `_gateway_call_model`, allow `failed_before_first_event` to resend `ModelRequestTimeout(setting="first_event_timeout")`, and update `model_call_error` for `ModelRequestTimeout`
  - Verification: `$ uv run pytest -q tests/ai/models/test_gateway_call.py tests/ai/client/test_roadmap_agent_run.py tests/invariants/test_k8s_manifests.py`

## 2. Generated configuration documents

> Kind: documents

- [x] 2.1 Run `uv run devops docs generate` to refresh `docs/CONFIGURATION.md` and `docs/ENV_VARS.md`
  - Verification: `$ uv run devops ci --check --no-cache --only docs`

Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).

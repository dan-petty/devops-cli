# Tasks

## 1. One resend layer for a pydantic-ai gateway call (behavior)

- [x] 1.1 Write failing tests: a fake gateway that answers 200 and ends the stream, or sends an error frame, before the first event gets one more call; an error after the first event, a status of the gateway and a 401 get none; each failed connect is sent at most `ai.max_retries` + 1 times; the gateway client has no retry transport
  - Verification: `$ uv run devops ci test tests/ai/models/test_gateway_call.py tests/ai/retries/test_pydantic_ai_retries.py`
- [x] 1.2 Add `GatewayCallModel` (`src/devops_cli/ai/models/gateway.py`), wrap each gateway chat model in it in `pydantic_ai_bridge`, build the gateway chat client with no retry transport, and delete `StreamRetryModel` with its helpers and tests
  - Verification: `$ uv run devops ci test tests/ai/models/test_gateway_call.py tests/ai/retries/test_pydantic_ai_retries.py tests/telemetry/test_library_spans.py`

## 2. One deadline per call (behavior)

- [x] 2.1 Write failing tests: a gateway chat model holds `request_timeout` from `ai.request_timeout_seconds` and `max_retries` 0; a second send that does not answer ends at the one deadline; the settings refuse an implement call deadline above the step limit
  - Verification: `$ uv run devops ci test tests/ai/models/test_gateway_call.py tests/roadmap/implement/test_roadmap_implement_timeouts.py`
- [x] 2.2 Add the setting `ai.request_timeout_seconds` and the check of `roadmap.implement.request_timeout_seconds` against `step_time_limit_seconds`
  - Verification: `$ uv run devops ci test tests/ai/models/test_gateway_call.py tests/roadmap/implement/test_roadmap_implement_timeouts.py tests/roadmap/implement/test_roadmap_implement_limits.py`

## 3. The direct client resends only a failed connect to the gateway (behavior)

- [x] 3.1 Write failing tests: `LLMClient` with provider `gateway` sends a call that gets 503 once, and a call whose connect fails `ai.max_retries` + 1 times
  - Verification: `$ uv run devops ci test tests/http/test_gateway_review_stall.py`
- [x] 3.2 Give the transport of a gateway client a retry rule for a failed connect only
  - Verification: `$ uv run devops ci test tests/http/test_gateway_review_stall.py tests/ai/client/test_ai_client_retries.py tests/http/test_entry.py tests/ai/spend/test_ai_spend_dispatch.py tests/roadmap/refine/test_roadmap_refine_failure_class.py tests/roadmap/refine/test_roadmap_refine_gateway_failures.py`

## 4. The gateway attempt nests inside the call deadline (manifests)

- [x] 4.1 Set the router `timeout` of `k8s/llm/gateway/config.yaml` to 900 s, below the default call deadlines, and turn the invariant test of #2869 to the new order
  - Verification: `$ uv run devops ci test tests/invariants/test_k8s_manifests.py tests/ai/benchmark/test_k8s_llm_gateway.py`

## 5. Documents

- [x] 5.1 Update the retry and timeout text of `k8s/README.md`, the setting descriptions and the generated reference documents
  - Verification: `$ uv run devops ci docs`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

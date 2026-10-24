# Tasks

## 1. Failing tests for failed gateway attempts and resolved model recording

- [x] 1.1 Add `route_retrying_client` in `tests/llm_stream_fakes.py`, write tests for chat dispatch failed attempts (500 retries, read timeouts, connection errors, and exhausted retries), stream failed attempts, and resolved model recording in `tests/test_ai_spend_dispatch.py`, and verify that they fail on the base (`uv run devops ci test tests/test_ai_spend_dispatch.py`)

## 2. Implementation of AttemptRecordingTransport and resolved model recording

- [x] 2.1 Implement `AttemptRecordingTransport` in `src/devops_cli/ai/spend/transport.py`, define `active_dispatch_context` in `src/devops_cli/ai/client/network.py`, wrap egress transport in `src/devops_cli/http/client.py`, and set dispatch context in `src/devops_cli/ai/client/unified.py` (`uv run devops ci test tests/test_ai_spend_dispatch.py`)
- [x] 2.2 Capture resolved model from reply JSON body in `src/devops_cli/ai/client/unified.py` and stream frames in `src/devops_cli/ai/client/streaming.py` when headers omit it (`uv run devops ci test tests/test_ai_spend_dispatch.py tests/test_ai_served_by.py`)
- [x] 2.3 Update `k8s/README.md` to document that the HTTP transport is the single retry layer (`uv run devops docs check`)

## 3. Full gate and OpenSpec archive

- [x] 3.1 Verify all tests and static checks pass (`uv run devops ci`)
- [x] 3.2 Archive OpenSpec change (`uv run devops openspec archive 1019-spend-ledger-failed-gateway-attempts`)

## Workflow follow-up

- Pending a person: measure the gap on one branch review before code change.
- Pending a person: repeat the measurement after the fix on one review.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

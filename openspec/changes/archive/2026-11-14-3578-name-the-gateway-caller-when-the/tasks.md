# Tasks

## 1. Send a non-empty end-user value

Kind: behavior. Reads: `src/devops_cli/ai/client/network.py`, `src/devops_cli/telemetry/tracer.py`. Changes: `src/devops_cli/ai/client/network.py`, `tests/ai/client/test_gateway_caller_headers.py`.

- [x] 1.1 Fall back to `CONST_OTEL_SERVICE_NAME` when the OTel service name is empty
  - Verification: `$ uv run devops ci test tests/ai/client/test_gateway_caller_headers.py` passes
- [x] 1.2 Add the empty service name to the header test, which covers the chat, embedding and agent paths
  - Verification: `$ uv run devops ci test tests/ai/client/test_gateway_caller_headers.py` passes

## 2. Run the gates

Kind: other. Reads: `tests/ai/`. Changes: none.

- [x] 2.1 Run the gate of the branch
  - Verification: `$ uv run devops ci test tests/ai/client` passes
  - Verification: `$ uv run devops ci --check --only lint,format,typecheck` passes

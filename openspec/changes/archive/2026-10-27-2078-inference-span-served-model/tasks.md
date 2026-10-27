# Tasks

## 1. Inference span names the deployment model that served the call

- [x] 1.1 Add `tests/test_ai_client_telemetry.py::test_a_gateway_dispatch_span_names_the_deployment_model_that_served_the_call`, asserting a gateway reply naming `openai/gpt-4o` sets `gen_ai.response.model` to `openai/gpt-4o` and `gen_ai.request.model` to the route name `devops-chat`, and add `test_a_gateway_dispatch_span_keeps_the_body_model_when_the_gateway_names_none`, asserting a gateway reply naming no deployment model keeps the reply-body model in `gen_ai.response.model`; verify both fail before the fix with `uv run devops ci test tests/test_ai_client_telemetry.py`.
- [x] 1.2 Change `_set_response_span_attributes` in `src/devops_cli/ai/client/unified.py` to set `gen_ai.response.model` to `LLMResponse.served_model` when it is present and to `LLMResponse.model` when it is absent, keeping `gen_ai.request.model` at the model the client asked for; verify the two new tests pass with `uv run devops ci test tests/test_ai_client_telemetry.py`.
- [x] 1.3 Regenerate the docs with `devops docs generate --sync-readme`; verify the diff is empty.

## Workflow follow-up

- Record the fix's fail-to-pass check run with `devops ci fail-to-pass --base main`.
- Archive the change with `uv run devops openspec archive 2078-inference-span-served-model` in the last commit.
- Open a draft pull request with `devops pr create`, watching it with `devops pr monitor <pr_number>` and marking it ready with `devops pr ready <pr_number>` only after the checks pass.
- Pending a person: review the diff in tuicr (tuicr -r main..HEAD).
- Pending a person: merge the pull request.

# Tasks

## 1. Collector key rule

- [x] 1.1 Add `request.key`, `request.callback_vars` and `response.data` to `GATEWAY_KEY_ATTRIBUTES` in `tests/gate/k8s_checks/otel_collector.py`
  - Verification: `$ uv run devops ci --only k8s`
- [x] 1.2 Add the `request.*` and `response.*` delete statement for `llm-gateway` spans to `transform/key_data` in `k8s/otel/values.yaml`
  - Verification: `$ uv run devops ci --only k8s`

## 2. Documents

- [x] 2.1 Name the `request.*` and `response.*` attributes of management spans in the "Gateway spans" section of `k8s/README.md`
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Pending a person: after the merge, check the Collector rollout and run the live TraceQL check in the pull request comment.

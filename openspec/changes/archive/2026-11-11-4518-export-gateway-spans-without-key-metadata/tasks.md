# Tasks

## 1. Gateway span export

- [x] 1.1 Add the checks of the callback, the Collector endpoint and the egress rule to `tests/gate/k8s_checks/llm_gateway.py`
  - Verification: `$ uv run devops ci --only k8s`
- [x] 1.2 Admit the Collector peer on TCP 4318 in the egress test of `tests/ai/benchmark/test_k8s_llm_gateway.py`
  - Verification: `$ uv run devops ci test tests/ai/benchmark/test_k8s_llm_gateway.py`
- [x] 1.3 Add the `otel` callback and `turn_off_message_logging` to `k8s/llm/gateway/config.yaml`, the `OTEL_*` variables to `k8s/llm/gateway/deployment.yaml`, and the Collector egress rule to `k8s/llm/gateway/networkpolicy.yaml`
  - Verification: `$ uv run devops ci --only k8s`

## 2. Collector key rule

- [x] 2.1 Add the check of the trace pipeline in `tests/gate/k8s_checks/otel_collector.py`
  - Verification: `$ uv run devops ci --only k8s`
- [x] 2.2 Add `transform/key_data` to the traces pipeline of `k8s/otel/values.yaml`, and name the real Service in its comment
  - Verification: `$ uv run devops ci --only k8s`

## 3. Documents

- [x] 3.1 Add the "Gateway spans" section to `k8s/README.md`
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Pending a person: after the merge, check the rollout and run the live TraceQL checks in the pull request comment.
